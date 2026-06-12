from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime
from typing import Any, AsyncIterator

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.models import GroupChat
from summary_relay_bot.db.repositories import (
    advance_summary_cursor_if_current,
    create_pending_manual_summary_job,
    create_running_summary_job,
    create_summary_result,
    ensure_summary_state,
    finish_summary_job,
    get_active_summary_job,
    get_group_by_chat_id,
    get_summary_job_for_group,
    mark_summary_job_running,
    messages_after_sequence,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.llm.client import PrivacyAwareSummaryClient, SummaryLLMError
from summary_relay_bot.services.group_settings import enabled_group_settings, group_summary_settings
from summary_relay_bot.services.runtime_config import (
    RuntimeConfigError,
    SummaryProfileRuntimeConfig,
    load_summary_profile_runtime_config,
)
from summary_relay_bot.services.secrets import SecretError, SecretService
from summary_relay_bot.services.summary_content import render_admin_summary, render_no_new_messages
from summary_relay_bot.telegram.errors import classify_telegram_error


@dataclass(frozen=True, slots=True)
class SummaryRunResult:
    chat_id: int
    status: str
    message: str
    cursor_advanced: bool = False


class SummaryJobNotFoundError(ValueError):
    pass


class SummaryJobConflictError(ValueError):
    def __init__(self, active_job_id: int) -> None:
        super().__init__("summary job already active")
        self.active_job_id = active_job_id


class BotRuntimeReloadInProgressError(RuntimeError):
    pass


class SummaryReloadGate:
    def __init__(self) -> None:
        self._active_bot_delivery_summaries = 0
        self._runtime_reload_active = False
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def enter_bot_delivery_summary(self) -> AsyncIterator[None]:
        async with self._condition:
            if self._runtime_reload_active:
                raise BotRuntimeReloadInProgressError("bot runtime is reloading")
            self._active_bot_delivery_summaries += 1
        try:
            yield
        finally:
            async with self._condition:
                self._active_bot_delivery_summaries -= 1
                self._condition.notify_all()

    async def has_active_bot_delivery_summary(self) -> bool:
        async with self._condition:
            return self._active_bot_delivery_summaries > 0

    async def try_begin_runtime_reload(self) -> bool:
        async with self._condition:
            if self._active_bot_delivery_summaries > 0 or self._runtime_reload_active:
                return False
            self._runtime_reload_active = True
            return True

    async def finish_runtime_reload(self) -> None:
        async with self._condition:
            self._runtime_reload_active = False
            self._condition.notify_all()


@dataclass(frozen=True, slots=True)
class SummaryJobResultView:
    id: int
    prompt_version: str
    llm_provider_id: int | None
    summary_profile_id: int | None
    model: str | None
    interval_start_sequence: int
    interval_end_sequence: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class SummaryJobView:
    id: int
    group_id: int
    chat_id: int
    trigger_type: str
    status: str
    starting_sequence: int
    cutoff_sequence: int | None
    prompt_version: str | None
    llm_provider_id: int | None
    summary_profile_id: int | None
    model: str | None
    error_type: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    result: SummaryJobResultView | None = None


def _job_view(job) -> SummaryJobView:
    result = job.__dict__.get("result")
    return SummaryJobView(
        id=job.id,
        group_id=job.group_id,
        chat_id=job.chat_id,
        trigger_type=job.trigger_type,
        status=job.status,
        starting_sequence=job.starting_sequence,
        cutoff_sequence=job.cutoff_sequence,
        prompt_version=job.prompt_version,
        llm_provider_id=job.llm_provider_id,
        summary_profile_id=job.summary_profile_id,
        model=job.model,
        error_type=job.error_type,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=(
            SummaryJobResultView(
                id=result.id,
                prompt_version=result.prompt_version,
                llm_provider_id=result.llm_provider_id,
                summary_profile_id=result.summary_profile_id,
                model=result.model,
                interval_start_sequence=result.interval_start_sequence,
                interval_end_sequence=result.interval_end_sequence,
                created_at=result.created_at,
            )
            if result is not None
            else None
        ),
    )


async def run_manual_summary(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    secret_service: SecretService,
    requested_chat_id: int | None = None,
    reload_gate: SummaryReloadGate | None = None,
) -> str:
    if requested_chat_id is not None:
        group = await get_group_by_chat_id(session, requested_chat_id)
        groups = [group] if group else []
    else:
        groups = [settings.group for settings in await enabled_group_settings(session)]

    if not groups:
        if requested_chat_id is None:
            return "No enabled groups are available for summary. Use /groups and /enable_group first."
        return f"Group {requested_chat_id} is not known yet."

    results: list[SummaryRunResult] = []
    for group in groups:
        results.append(
            await run_summary_for_group(
                session=session,
                bot=bot,
                owner_id=owner_id,
                secret_service=secret_service,
                group=group,
                trigger_type="manual",
                notify_no_messages=True,
                reload_gate=reload_gate,
            )
        )
    return "\n".join(f"{result.chat_id} [{result.status}]: {result.message}" for result in results)


async def run_scheduled_summary(
    *,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    secret_service: SecretService,
    owner_id: int,
    chat_id: int,
    reload_gate: SummaryReloadGate | None = None,
) -> SummaryRunResult:
    async with session_scope(session_factory) as session:
        group = await get_group_by_chat_id(session, chat_id)
        settings = await group_summary_settings(session, group=group) if group is not None else None
        if group is None or settings is None or not settings.enabled:
            return SummaryRunResult(chat_id=chat_id, status="skipped", message="group is disabled")
        return await run_summary_for_group(
            session=session,
            bot=bot,
            owner_id=owner_id,
            secret_service=secret_service,
            group=group,
            trigger_type="scheduled",
            notify_no_messages=False,
            reload_gate=reload_gate,
        )


async def run_summary_for_group(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    secret_service: SecretService,
    group: GroupChat,
    trigger_type: str,
    notify_no_messages: bool,
    reload_gate: SummaryReloadGate | None = None,
) -> SummaryRunResult:
    if reload_gate is not None:
        try:
            async with reload_gate.enter_bot_delivery_summary():
                return await _run_summary_for_group(
                    session=session,
                    bot=bot,
                    owner_id=owner_id,
                    secret_service=secret_service,
                    group=group,
                    trigger_type=trigger_type,
                    notify_no_messages=notify_no_messages,
                )
        except BotRuntimeReloadInProgressError:
            return SummaryRunResult(
                chat_id=group.chat_id,
                status="blocked",
                message="bot runtime is reloading",
            )
    return await _run_summary_for_group(
        session=session,
        bot=bot,
        owner_id=owner_id,
        secret_service=secret_service,
        group=group,
        trigger_type=trigger_type,
        notify_no_messages=notify_no_messages,
    )


async def _run_summary_for_group(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    secret_service: SecretService,
    group: GroupChat,
    trigger_type: str,
    notify_no_messages: bool,
) -> SummaryRunResult:
    state = await ensure_summary_state(session, group)
    job = await create_running_summary_job(
        session,
        group=group,
        trigger_type=trigger_type,
        starting_sequence=state.last_summary_sequence,
    )
    if job is None:
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="blocked",
            message="summary already running",
        )

    try:
        runtime_profile = await load_summary_profile_runtime_config(
            session,
            secret_service=secret_service,
            group=group,
        )
    except (RuntimeConfigError, SecretError) as exc:
        await finish_summary_job(
            session,
            job,
            "failed",
            cutoff_sequence=state.last_summary_sequence,
            error_type="runtime_config_error",
            error_message=str(exc),
        )
        await _notify_failure(bot, owner_id, group.chat_id, "Runtime summary config failed")
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="failed",
            message="runtime summary config failed; cursor unchanged",
        )

    _apply_runtime_profile(job, runtime_profile)
    await session.flush()

    messages = list(
        await messages_after_sequence(
            session,
            group=group,
            sequence=state.last_summary_sequence,
        )
    )
    if not messages:
        await finish_summary_job(session, job, "succeeded", cutoff_sequence=state.last_summary_sequence)
        message = render_no_new_messages(group.title) if notify_no_messages else "no new messages"
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="succeeded",
            message=message,
        )

    cutoff_sequence = max(message.id for message in messages)
    llm_client = PrivacyAwareSummaryClient(runtime_profile)
    try:
        summary_text = await llm_client.summarize_group_messages(
            group_title=group.title,
            group_messages=messages,
        )
    except SummaryLLMError as exc:
        await finish_summary_job(
            session,
            job,
            "failed",
            cutoff_sequence=cutoff_sequence,
            error_type="llm_failed",
            error_message=str(exc),
        )
        await _notify_failure(bot, owner_id, group.chat_id, "LLM summary failed")
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="failed",
            message="LLM summary failed; cursor unchanged",
        )

    try:
        delivered = await bot.send_message(
            owner_id,
            render_admin_summary(group.title, summary_text),
        )
    except Exception as exc:
        failure = classify_telegram_error(exc)
        job_status = "failed" if failure.retryable else "blocked"
        await finish_summary_job(
            session,
            job,
            job_status,
            cutoff_sequence=cutoff_sequence,
            error_type=failure.error_type,
            error_message=failure.message,
        )
        return SummaryRunResult(
            chat_id=group.chat_id,
            status=job_status,
            message=f"Telegram delivery {job_status}; cursor unchanged",
        )

    advanced = await advance_summary_cursor_if_current(
        session,
        state=state,
        expected_sequence=job.starting_sequence,
        new_sequence=cutoff_sequence,
    )
    if not advanced:
        await finish_summary_job(
            session,
            job,
            "failed",
            cutoff_sequence=cutoff_sequence,
            error_type="stale_cursor",
            error_message="summary state cursor changed before delivery result could advance it",
        )
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="failed",
            message="cursor changed during summary; delivered summary was not marked successful",
        )

    await create_summary_result(
        session,
        job=job,
        group=group,
        summary_text=summary_text,
        delivered_admin_chat_id=owner_id,
        delivered_message_id=getattr(delivered, "message_id", None),
        prompt_version=runtime_profile.prompt_version,
        llm_provider_id=runtime_profile.llm_provider.llm_provider_id,
        summary_profile_id=runtime_profile.summary_profile_id,
        model=runtime_profile.model,
        interval_start_sequence=job.starting_sequence,
        interval_end_sequence=cutoff_sequence,
    )
    await finish_summary_job(session, job, "succeeded", cutoff_sequence=cutoff_sequence)
    return SummaryRunResult(
        chat_id=group.chat_id,
        status="succeeded",
        message="summary delivered and cursor advanced",
        cursor_advanced=True,
    )


async def _notify_failure(bot: Bot, owner_id: int, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(owner_id, f"{text} for group {chat_id}. Cursor was not advanced.")
    except Exception:
        pass


def _apply_runtime_profile(job, runtime_profile: SummaryProfileRuntimeConfig) -> None:
    job.prompt_version = runtime_profile.prompt_version
    job.llm_provider_id = runtime_profile.llm_provider.llm_provider_id
    job.summary_profile_id = runtime_profile.summary_profile_id
    job.model = runtime_profile.model


async def create_manual_summary_job(
    session: AsyncSession,
    *,
    group: GroupChat,
) -> SummaryJobView:
    state = await ensure_summary_state(session, group)
    job = await create_pending_manual_summary_job(
        session,
        group=group,
        starting_sequence=state.last_summary_sequence,
    )
    if job is None:
        active_job = await get_active_summary_job(session, group_id=group.id)
        active_job_id = active_job.id if active_job is not None else 0
        raise SummaryJobConflictError(active_job_id)
    return _job_view(job)


async def get_summary_job_status(
    session: AsyncSession,
    *,
    group: GroupChat,
    job_id: int,
) -> SummaryJobView:
    job = await get_summary_job_for_group(session, group_id=group.id, job_id=job_id)
    if job is None:
        raise SummaryJobNotFoundError("summary job not found")
    return _job_view(job)


def schedule_manual_summary_job(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    secret_service: SecretService,
    group_id: int,
    job_id: int,
) -> None:
    asyncio.create_task(
        run_web_manual_summary_job(
            session_factory=session_factory,
            secret_service=secret_service,
            group_id=group_id,
            job_id=job_id,
        ),
        name=f"web-manual-summary:{group_id}:{job_id}",
    )


async def run_web_manual_summary_job(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    secret_service: SecretService,
    group_id: int,
    job_id: int,
) -> None:
    async with session_scope(session_factory) as session:
        group = await session.get(GroupChat, group_id)
        job = await get_summary_job_for_group(session, group_id=group_id, job_id=job_id)
        if group is None or job is None:
            return
        if not await mark_summary_job_running(session, job):
            return

        try:
            runtime_profile = await load_summary_profile_runtime_config(
                session,
                secret_service=secret_service,
                group=group,
            )
        except (RuntimeConfigError, SecretError) as exc:
            await finish_summary_job(
                session,
                job,
                "failed",
                cutoff_sequence=job.starting_sequence,
                error_type="runtime_config_error",
                error_message=str(exc),
            )
            return

        _apply_runtime_profile(job, runtime_profile)
        await session.flush()

        state = await ensure_summary_state(session, group)
        messages = list(
            await messages_after_sequence(
                session,
                group=group,
                sequence=state.last_summary_sequence,
            )
        )
        if not messages:
            await finish_summary_job(session, job, "succeeded", cutoff_sequence=state.last_summary_sequence)
            return

        cutoff_sequence = max(message.id for message in messages)
        llm_client = PrivacyAwareSummaryClient(runtime_profile)
        try:
            summary_text = await llm_client.summarize_group_messages(
                group_title=group.title,
                group_messages=messages,
            )
        except SummaryLLMError as exc:
            await finish_summary_job(
                session,
                job,
                "failed",
                cutoff_sequence=cutoff_sequence,
                error_type="llm_failed",
                error_message=str(exc),
            )
            return

        advanced = await advance_summary_cursor_if_current(
            session,
            state=state,
            expected_sequence=job.starting_sequence,
            new_sequence=cutoff_sequence,
        )
        if not advanced:
            await finish_summary_job(
                session,
                job,
                "failed",
                cutoff_sequence=cutoff_sequence,
                error_type="stale_cursor",
                error_message="summary state cursor changed before result could advance it",
            )
            return

        await create_summary_result(
            session,
            job=job,
            group=group,
            summary_text=summary_text,
            delivered_admin_chat_id=None,
            delivered_message_id=None,
            prompt_version=runtime_profile.prompt_version,
            llm_provider_id=runtime_profile.llm_provider.llm_provider_id,
            summary_profile_id=runtime_profile.summary_profile_id,
            model=runtime_profile.model,
            interval_start_sequence=job.starting_sequence,
            interval_end_sequence=cutoff_sequence,
        )
        await finish_summary_job(session, job, "succeeded", cutoff_sequence=cutoff_sequence)
