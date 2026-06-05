from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.models import GroupChat
from summary_relay_bot.db.repositories import (
    advance_summary_cursor_if_current,
    create_running_summary_job,
    create_summary_result,
    ensure_summary_state,
    finish_summary_job,
    get_group_by_chat_id,
    list_groups,
    messages_after_sequence,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.llm.client import PrivacyAwareSummaryClient, SummaryLLMError
from summary_relay_bot.services.summary_content import render_admin_summary, render_no_new_messages
from summary_relay_bot.telegram.errors import classify_telegram_error


@dataclass(frozen=True, slots=True)
class SummaryRunResult:
    chat_id: int
    status: str
    message: str
    cursor_advanced: bool = False


async def run_manual_summary(
    *,
    session: AsyncSession,
    bot: Bot,
    config: AppConfig,
    requested_chat_id: int | None = None,
) -> str:
    if requested_chat_id is not None:
        group = await get_group_by_chat_id(session, requested_chat_id)
        groups = [group] if group else []
    else:
        groups = [group for group in await list_groups(session) if group.summaries_enabled]

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
                config=config,
                group=group,
                trigger_type="manual",
                notify_no_messages=True,
            )
        )
    return "\n".join(f"{result.chat_id} [{result.status}]: {result.message}" for result in results)


async def run_scheduled_summary(
    *,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
    config: AppConfig,
    chat_id: int,
) -> SummaryRunResult:
    async with session_scope(session_factory) as session:
        group = await get_group_by_chat_id(session, chat_id)
        if group is None or not group.summaries_enabled:
            return SummaryRunResult(chat_id=chat_id, status="skipped", message="group is disabled")
        return await run_summary_for_group(
            session=session,
            bot=bot,
            config=config,
            group=group,
            trigger_type="scheduled",
            notify_no_messages=False,
        )


async def run_summary_for_group(
    *,
    session: AsyncSession,
    bot: Bot,
    config: AppConfig,
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
        prompt_version=config.summary_prompt_version,
    )
    if job is None:
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="blocked",
            message="summary already running",
        )

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
    llm_client = PrivacyAwareSummaryClient(config)
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
        await _notify_failure(bot, config.owner_id, group.chat_id, "LLM summary failed")
        return SummaryRunResult(
            chat_id=group.chat_id,
            status="failed",
            message="LLM summary failed; cursor unchanged",
        )

    try:
        delivered = await bot.send_message(
            config.owner_id,
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
        delivered_admin_chat_id=config.owner_id,
        delivered_message_id=getattr(delivered, "message_id", None),
        prompt_version=config.summary_prompt_version,
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
