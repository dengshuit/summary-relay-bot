from __future__ import annotations

import asyncio
from types import SimpleNamespace

from sqlalchemy import select

from summary_relay_bot.db.models import SummaryDeliveryAttempt, SummaryResult
from summary_relay_bot.db.repositories import (
    create_running_summary_job,
    create_summary_result,
    ensure_summary_state,
    finish_summary_job,
    upsert_group,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.summary_notifications import (
    SummaryNotificationDispatcher,
    deliver_summary_notification,
    split_telegram_text,
)


class FakeSender:
    def __init__(self, *, failures: int = 0, delay: float = 0) -> None:
        self.failures = failures
        self.delay = delay
        self.sent: list[tuple[int, str]] = []
        self.active = 0
        self.max_active = 0

    async def send_message(self, chat_id: int, text: str):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        try:
            if self.delay:
                await asyncio.sleep(self.delay)
            if self.failures > 0:
                self.failures -= 1
                raise TimeoutError("temporary timeout")
            self.sent.append((chat_id, text))
            return SimpleNamespace(message_id=len(self.sent))
        finally:
            self.active -= 1


class FailingOnTextSender:
    def __init__(self, failure_text: str) -> None:
        self.failure_text = failure_text
        self.failed_once = False
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str):
        if text == self.failure_text and not self.failed_once:
            self.failed_once = True
            raise TimeoutError("temporary chunk failure")
        self.sent.append((chat_id, text))
        return SimpleNamespace(message_id=len(self.sent))


async def _seed_result(session, *, text: str = "summary text") -> SummaryResult:
    group = await upsert_group(session, chat_id=-100, chat_type="group", title="Group")
    state = await ensure_summary_state(session, group)
    job = await create_running_summary_job(
        session,
        group=group,
        trigger_type="manual",
        starting_sequence=state.last_summary_sequence,
    )
    assert job is not None
    result = await create_summary_result(
        session,
        job=job,
        group=group,
        summary_text=text,
        delivered_admin_chat_id=None,
        delivered_message_id=None,
        prompt_version="v1",
        interval_start_sequence=0,
        interval_end_sequence=1,
    )
    await finish_summary_job(session, job, "succeeded", cutoff_sequence=1)
    return result


def test_split_telegram_text_preserves_content_and_bounds_chunks() -> None:
    text = "a" * 50 + "\n" + "b" * 50 + "\n" + "c" * 50

    chunks = split_telegram_text(text, limit=60)

    assert all(len(chunk) <= 60 for chunk in chunks)
    assert "\n".join(chunks) == text


async def test_deliver_summary_notification_sends_all_chunks_and_records_success(session_factory) -> None:
    async with session_scope(session_factory) as session:
        result = await _seed_result(session, text="x" * 90)
        result_id = result.id
    sender = FakeSender()

    await deliver_summary_notification(
        session_factory=session_factory,
        sender=sender,
        owner_id=1001,
        summary_result_id=result_id,
        chunk_limit=40,
    )

    async with session_factory() as session:
        [attempt] = (await session.scalars(select(SummaryDeliveryAttempt))).all()
    assert attempt.status == "succeeded"
    assert attempt.attempt_count == 1
    assert attempt.total_chunks > 1
    assert attempt.sent_chunks == attempt.total_chunks
    assert attempt.telegram_message_ids == list(range(1, attempt.total_chunks + 1))
    assert "".join(text for _chat_id, text in sender.sent).replace("\n", "").endswith("x" * 90)


async def test_deliver_summary_notification_records_skipped_without_sender(session_factory) -> None:
    async with session_scope(session_factory) as session:
        result = await _seed_result(session)
        result_id = result.id

    await deliver_summary_notification(
        session_factory=session_factory,
        sender=None,
        owner_id=1001,
        summary_result_id=result_id,
    )

    async with session_factory() as session:
        [attempt] = (await session.scalars(select(SummaryDeliveryAttempt))).all()
    assert attempt.status == "skipped"
    assert attempt.error_type == "relay_unavailable"
    assert attempt.attempt_count == 0


async def test_deliver_summary_notification_retries_timeout_and_can_succeed(session_factory) -> None:
    async with session_scope(session_factory) as session:
        result = await _seed_result(session)
        result_id = result.id
    sender = FakeSender(failures=1)

    await deliver_summary_notification(
        session_factory=session_factory,
        sender=sender,
        owner_id=1001,
        summary_result_id=result_id,
        max_attempts=3,
        timeout_seconds=1,
    )

    async with session_factory() as session:
        [attempt] = (await session.scalars(select(SummaryDeliveryAttempt))).all()
    assert attempt.status == "succeeded"
    assert attempt.attempt_count == 2
    assert attempt.sent_chunks == 1


async def test_deliver_summary_notification_resumes_after_sent_chunks(session_factory) -> None:
    async with session_scope(session_factory) as session:
        result = await _seed_result(session, text="a" * 30 + "\n" + "b" * 30)
        result_id = result.id
    sender = FailingOnTextSender("b" * 30)

    await deliver_summary_notification(
        session_factory=session_factory,
        sender=sender,
        owner_id=1001,
        summary_result_id=result_id,
        max_attempts=3,
        timeout_seconds=1,
        chunk_limit=40,
    )

    async with session_factory() as session:
        [attempt] = (await session.scalars(select(SummaryDeliveryAttempt))).all()
    sent_texts = [text for _chat_id, text in sender.sent]
    assert attempt.status == "succeeded"
    assert attempt.attempt_count == 2
    assert attempt.sent_chunks == attempt.total_chunks
    assert sent_texts.count("a" * 30) == 1
    assert sent_texts.count("b" * 30) == 1


async def test_deliver_summary_notification_records_timeout_after_retry_exhaustion(session_factory) -> None:
    async with session_scope(session_factory) as session:
        result = await _seed_result(session)
        result_id = result.id
    sender = FakeSender(delay=0.05)

    await deliver_summary_notification(
        session_factory=session_factory,
        sender=sender,
        owner_id=1001,
        summary_result_id=result_id,
        max_attempts=2,
        timeout_seconds=0.01,
    )

    async with session_factory() as session:
        [attempt] = (await session.scalars(select(SummaryDeliveryAttempt))).all()
    assert attempt.status == "timeout"
    assert attempt.attempt_count == 2
    assert attempt.error_type == "timeout"


async def test_summary_notification_dispatcher_bounds_concurrency(session_factory) -> None:
    result_ids: list[int] = []
    async with session_scope(session_factory) as session:
        for index in range(3):
            result = await _seed_result(session, text=f"summary {index}")
            result_ids.append(result.id)
    sender = FakeSender(delay=0.01)
    dispatcher = SummaryNotificationDispatcher(
        session_factory=session_factory,
        sender=sender,
        owner_id=1001,
        max_concurrency=1,
        timeout_seconds=1,
    )

    for result_id in result_ids:
        dispatcher.schedule(result_id)
    await dispatcher.drain()

    async with session_factory() as session:
        attempts = (await session.scalars(select(SummaryDeliveryAttempt))).all()
    assert sender.max_active == 1
    assert len(attempts) == 3
    assert {attempt.status for attempt in attempts} == {"succeeded"}
