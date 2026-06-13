from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from summary_relay_bot.db.models import SummaryJob, SummaryResult
from summary_relay_bot.db.repositories import (
    create_summary_delivery_attempt,
    latest_summary_delivery_attempt,
    update_summary_delivery_attempt,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.summary_content import render_admin_summary
from summary_relay_bot.telegram.errors import classify_telegram_error


TELEGRAM_TEXT_LIMIT = 4096
DEFAULT_CHUNK_LIMIT = 3900
DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MAX_CONCURRENCY = 2


class SummaryNotificationSender(Protocol):
    async def send_message(self, chat_id: int, text: str) -> Any: ...


@dataclass(frozen=True, slots=True)
class SummaryDeliveryView:
    status: str
    attempt_count: int
    max_attempts: int
    total_chunks: int
    sent_chunks: int
    error_type: str | None
    error_message: str | None
    updated_at: object


def split_telegram_text(text: str, *, limit: int = DEFAULT_CHUNK_LIMIT) -> list[str]:
    if limit <= 0 or limit > TELEGRAM_TEXT_LIMIT:
        raise ValueError("chunk limit is invalid")
    if text == "":
        return [""]

    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            chunks.append(remaining)
            break
        split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at <= 0:
            split_at = limit
        chunks.append(remaining[:split_at])
        remaining = remaining[split_at:]
        if remaining.startswith("\n"):
            remaining = remaining[1:]
    return chunks


async def _send_chunks(
    *,
    sender: SummaryNotificationSender,
    target_chat_id: int,
    chunks: list[str],
    start_index: int = 0,
    on_chunk_sent: Callable[[int, int | None], Awaitable[None]] | None = None,
) -> list[int]:
    message_ids: list[int] = []
    for index, chunk in enumerate(chunks[start_index:], start=start_index):
        delivered = await sender.send_message(target_chat_id, chunk)
        message_id = getattr(delivered, "message_id", None)
        if message_id is not None:
            message_id = int(message_id)
            message_ids.append(message_id)
        if on_chunk_sent is not None:
            await on_chunk_sent(index + 1, message_id)
    return message_ids


async def deliver_summary_notification(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    sender: SummaryNotificationSender | None,
    owner_id: int | None,
    summary_result_id: int,
    relay_bot_id: int | None = None,
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    chunk_limit: int = DEFAULT_CHUNK_LIMIT,
) -> None:
    async with session_scope(session_factory) as session:
        result = await session.get(
            SummaryResult,
            summary_result_id,
            options=[selectinload(SummaryResult.job).selectinload(SummaryJob.group)],
        )
        if result is None:
            return
        group = result.job.group if result.job is not None else None
        chunks = split_telegram_text(
            render_admin_summary(group.title if group is not None else None, result.summary_text),
            limit=chunk_limit,
        )
        attempt = await create_summary_delivery_attempt(
            session,
            summary_result=result,
            relay_bot_id=relay_bot_id,
            target_chat_id=owner_id,
            max_attempts=max_attempts,
            timeout_seconds=timeout_seconds,
            total_chunks=len(chunks),
        )
        if sender is None or owner_id is None:
            await update_summary_delivery_attempt(
                session,
                attempt,
                status="skipped",
                error_type="relay_unavailable",
                error_message="private relay bot is unavailable",
                finished=True,
            )
            return

    last_error_type: str | None = None
    last_error_message: str | None = None
    last_status = "failed"
    sent_message_ids: list[int] = []
    for attempt_number in range(1, max_attempts + 1):
        async with session_scope(session_factory) as session:
            attempt = await latest_summary_delivery_attempt(session, summary_result_id=summary_result_id)
            if attempt is None:
                return
            sent_count = attempt.sent_chunks
            sent_message_ids = list(attempt.telegram_message_ids or sent_message_ids)
            if sent_count >= len(chunks):
                await update_summary_delivery_attempt(
                    session,
                    attempt,
                    status="succeeded",
                    attempt_count=max(attempt.attempt_count, attempt_number - 1),
                    sent_chunks=len(chunks),
                    telegram_message_ids=sent_message_ids,
                    finished=True,
                )
                return
            await update_summary_delivery_attempt(
                session,
                attempt,
                status="running",
                attempt_count=attempt_number,
                error_type=None,
                error_message=None,
                started=True,
            )

        async def record_chunk_sent(sent_chunks: int, message_id: int | None) -> None:
            if message_id is not None:
                sent_message_ids.append(message_id)
            async with session_scope(session_factory) as session:
                attempt = await latest_summary_delivery_attempt(session, summary_result_id=summary_result_id)
                if attempt is None:
                    return
                await update_summary_delivery_attempt(
                    session,
                    attempt,
                    status="running",
                    sent_chunks=sent_chunks,
                    telegram_message_ids=sent_message_ids,
                )

        try:
            async with asyncio.timeout(timeout_seconds):
                await _send_chunks(
                    sender=sender,
                    target_chat_id=owner_id,
                    chunks=chunks,
                    start_index=sent_count,
                    on_chunk_sent=record_chunk_sent,
                )
        except TimeoutError as exc:
            last_status = "timeout"
            last_error_type = "timeout"
            last_error_message = "summary notification delivery timed out"
            if attempt_number >= max_attempts:
                break
            continue
        except Exception as exc:
            failure = classify_telegram_error(exc)
            last_status = "failed"
            last_error_type = failure.error_type
            last_error_message = failure.message
            if not failure.retryable or attempt_number >= max_attempts:
                break
            continue

        async with session_scope(session_factory) as session:
            attempt = await latest_summary_delivery_attempt(session, summary_result_id=summary_result_id)
            if attempt is None:
                return
            await update_summary_delivery_attempt(
                session,
                attempt,
                status="succeeded",
                attempt_count=attempt_number,
                sent_chunks=len(chunks),
                telegram_message_ids=sent_message_ids,
                finished=True,
            )
        return

    async with session_scope(session_factory) as session:
        attempt = await latest_summary_delivery_attempt(session, summary_result_id=summary_result_id)
        if attempt is None:
            return
        await update_summary_delivery_attempt(
            session,
            attempt,
            status=last_status,
            sent_chunks=attempt.sent_chunks,
            telegram_message_ids=sent_message_ids or attempt.telegram_message_ids,
            error_type=last_error_type,
            error_message=last_error_message,
            finished=True,
        )


@dataclass(slots=True)
class SummaryNotificationDispatcher:
    session_factory: async_sessionmaker[AsyncSession]
    sender: SummaryNotificationSender | None
    owner_id: int | None
    relay_bot_id: int | None = None
    max_concurrency: int = DEFAULT_MAX_CONCURRENCY
    max_attempts: int = DEFAULT_MAX_ATTEMPTS
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    _tasks: set[asyncio.Task[None]] = field(default_factory=set, init=False, repr=False)
    _semaphore: asyncio.Semaphore = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._semaphore = asyncio.Semaphore(max(1, self.max_concurrency))

    @property
    def active_task_count(self) -> int:
        return len(self._tasks)

    def schedule(self, summary_result_id: int) -> None:
        task = asyncio.create_task(
            self._run(summary_result_id),
            name=f"summary-notification:{summary_result_id}",
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def drain(self) -> None:
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def _run(self, summary_result_id: int) -> None:
        async with self._semaphore:
            await deliver_summary_notification(
                session_factory=self.session_factory,
                sender=self.sender,
                owner_id=self.owner_id,
                relay_bot_id=self.relay_bot_id,
                summary_result_id=summary_result_id,
                max_attempts=self.max_attempts,
                timeout_seconds=self.timeout_seconds,
            )


SummaryNotificationScheduler = Callable[[int], None]
