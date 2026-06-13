from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from summary_relay_bot.db.models import (
    AdminReplyMap,
    DeliveryAttempt,
    GroupChat,
    GroupMessage,
    PrivateMessage,
    PrivateUser,
    SummaryJob,
    SummaryDeliveryAttempt,
    SummaryResult,
    SummaryState,
    SummaryUserbot,
    TelegramUpdate,
    utcnow,
)

ACTIVE_SUMMARY_JOB_STATUSES = ("pending", "running")
DEFAULT_SUMMARY_USERBOT_NAME = "legacy-bot-api-compat"


async def get_or_create_raw_update(
    session: AsyncSession,
    *,
    update_id: int,
    payload: dict[str, Any],
    status: str = "raw_persisted",
) -> tuple[TelegramUpdate, bool]:
    existing = await session.scalar(select(TelegramUpdate).where(TelegramUpdate.update_id == update_id))
    if existing:
        return existing, False

    raw_update = TelegramUpdate(update_id=update_id, processing_status=status)
    session.add(raw_update)
    await session.flush()
    return raw_update, True


async def mark_raw_update_status(
    session: AsyncSession,
    raw_update: TelegramUpdate,
    status: str,
    *,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    raw_update.processing_status = status
    raw_update.error_type = error_type
    raw_update.error_message = error_message
    raw_update.processed_at = utcnow()
    await session.flush()


async def pending_raw_updates(session: AsyncSession) -> Sequence[TelegramUpdate]:
    result = await session.scalars(
        select(TelegramUpdate).where(TelegramUpdate.processing_status.in_(["raw_persisted", "failed"]))
    )
    return result.all()


async def redact_raw_payloads_older_than(
    session: AsyncSession,
    *,
    older_than: datetime,
) -> int:
    return 0


async def _ensure_default_summary_userbot(session: AsyncSession) -> SummaryUserbot:
    userbot = await session.scalar(select(SummaryUserbot).order_by(SummaryUserbot.id).limit(1))
    if userbot is not None:
        return userbot
    userbot = SummaryUserbot(
        name=DEFAULT_SUMMARY_USERBOT_NAME,
        enabled=False,
        auth_status="unconfigured",
        runtime_status="disabled",
    )
    session.add(userbot)
    await session.flush()
    return userbot


async def upsert_group(
    session: AsyncSession,
    *,
    chat_id: int,
    chat_type: str,
    title: str | None,
    username: str | None = None,
) -> GroupChat:
    userbot = await _ensure_default_summary_userbot(session)
    group = await session.scalar(
        select(GroupChat).where(
            GroupChat.userbot_id == userbot.id,
            GroupChat.chat_id == chat_id,
        )
    )
    if group:
        group.chat_type = chat_type
        group.title = title
        group.username = username
        group.last_seen_at = utcnow()
        group.updated_at = utcnow()
        await session.flush()
        return group

    group = GroupChat(
        userbot_id=userbot.id,
        chat_id=chat_id,
        chat_type=chat_type,
        title=title,
        username=username,
        telegram_peer_type=chat_type,
        collection_status="disabled",
    )
    session.add(group)
    await session.flush()
    await ensure_summary_state(session, group)
    return group


async def list_groups(session: AsyncSession) -> Sequence[GroupChat]:
    result = await session.scalars(select(GroupChat).order_by(GroupChat.title, GroupChat.chat_id))
    return result.all()


async def get_group_by_chat_id(session: AsyncSession, chat_id: int) -> GroupChat | None:
    return await session.scalar(select(GroupChat).where(GroupChat.chat_id == chat_id))


async def get_enabled_userbot_group_by_chat_id(session: AsyncSession, chat_id: int) -> GroupChat | None:
    return await session.scalar(
        select(GroupChat)
        .join(SummaryUserbot, SummaryUserbot.id == GroupChat.userbot_id)
        .where(
            GroupChat.chat_id == chat_id,
            SummaryUserbot.enabled.is_(True),
        )
    )


async def store_group_message(
    session: AsyncSession,
    *,
    group: GroupChat,
    raw_update: TelegramUpdate,
    telegram_message_id: int,
    sender_user_id: int | None,
    sender_display_name: str | None,
    message_type: str,
    text: str | None,
    caption: str | None,
    summary_content: str,
    file_id: str | None = None,
    file_unique_id: str | None = None,
    file_name: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
    media_metadata: dict[str, Any] | None = None,
) -> tuple[GroupMessage, bool]:
    existing = await session.scalar(
        select(GroupMessage).where(
            GroupMessage.group_id == group.id,
            GroupMessage.telegram_message_id == telegram_message_id,
        )
    )
    if existing:
        return existing, False

    message = GroupMessage(
        group=group,
        userbot_id=group.userbot_id,
        telegram_message_id=telegram_message_id,
        sender_user_id=sender_user_id,
        sender_display_name=sender_display_name,
        message_type=message_type,
        text=text,
        caption=caption,
        summary_content=summary_content,
        file_name=file_name,
        mime_type=mime_type,
        file_size=file_size,
        media_metadata={
            **(media_metadata or {}),
            **({"file_id": file_id} if file_id is not None else {}),
            **({"file_unique_id": file_unique_id} if file_unique_id is not None else {}),
        }
        or None,
    )
    session.add(message)
    await session.flush()
    return message, True


async def upsert_private_user(
    session: AsyncSession,
    *,
    telegram_user_id: int,
    username: str | None,
    first_name: str | None,
    last_name: str | None,
    language_code: str | None = None,
) -> PrivateUser:
    private_user = await session.scalar(
        select(PrivateUser).where(PrivateUser.telegram_user_id == telegram_user_id)
    )
    if private_user:
        private_user.username = username
        private_user.first_name = first_name
        private_user.last_name = last_name
        private_user.language_code = language_code
        private_user.last_seen_at = utcnow()
        await session.flush()
        return private_user

    private_user = PrivateUser(
        telegram_user_id=telegram_user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        language_code=language_code,
    )
    session.add(private_user)
    await session.flush()
    return private_user


async def get_private_user_by_telegram_id(
    session: AsyncSession,
    telegram_user_id: int,
) -> PrivateUser | None:
    return await session.scalar(
        select(PrivateUser).where(PrivateUser.telegram_user_id == telegram_user_id)
    )


async def create_private_message(
    session: AsyncSession,
    *,
    private_user: PrivateUser,
    direction: str,
    telegram_chat_id: int,
    message_type: str,
    raw_update: TelegramUpdate | None = None,
    telegram_message_id: int | None = None,
    admin_message_id: int | None = None,
    text: str | None = None,
    caption: str | None = None,
    delivery_status: str = "stored",
    error_type: str | None = None,
    error_message: str | None = None,
) -> PrivateMessage:
    private_message = PrivateMessage(
        private_user=private_user,
        raw_update=raw_update,
        direction=direction,
        telegram_chat_id=telegram_chat_id,
        telegram_message_id=telegram_message_id,
        admin_message_id=admin_message_id,
        message_type=message_type,
        text=text,
        caption=caption,
        delivery_status=delivery_status,
        error_type=error_type,
        error_message=error_message,
    )
    session.add(private_message)
    await session.flush()
    return private_message


async def create_reply_map(
    session: AsyncSession,
    *,
    private_user: PrivateUser,
    admin_chat_id: int,
    admin_message_id: int,
    source_kind: str,
    private_message: PrivateMessage | None = None,
    status: str = "mapped",
) -> tuple[AdminReplyMap, bool]:
    existing = await session.scalar(
        select(AdminReplyMap).where(
            AdminReplyMap.admin_chat_id == admin_chat_id,
            AdminReplyMap.admin_message_id == admin_message_id,
        )
    )
    if existing:
        return existing, False

    reply_map = AdminReplyMap(
        private_user=private_user,
        private_message=private_message,
        admin_chat_id=admin_chat_id,
        admin_message_id=admin_message_id,
        source_kind=source_kind,
        status=status,
    )
    session.add(reply_map)
    await session.flush()
    return reply_map, True


async def find_reply_map(
    session: AsyncSession,
    *,
    admin_chat_id: int,
    admin_message_id: int,
) -> AdminReplyMap | None:
    return await session.scalar(
        select(AdminReplyMap)
        .options(selectinload(AdminReplyMap.private_user), selectinload(AdminReplyMap.private_message))
        .where(
            AdminReplyMap.admin_chat_id == admin_chat_id,
            AdminReplyMap.admin_message_id == admin_message_id,
        )
    )


async def create_delivery_attempt(
    session: AsyncSession,
    *,
    purpose: str,
    target_chat_id: int | None = None,
    source_chat_id: int | None = None,
    source_message_id: int | None = None,
    result_message_id: int | None = None,
    status: str = "pending",
    error_type: str | None = None,
    error_message: str | None = None,
) -> DeliveryAttempt:
    attempt = DeliveryAttempt(
        purpose=purpose,
        target_chat_id=target_chat_id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        result_message_id=result_message_id,
        status=status,
        error_type=error_type,
        error_message=error_message,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def mark_delivery_attempt_status(
    session: AsyncSession,
    attempt: DeliveryAttempt,
    status: str,
    *,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    attempt.status = status
    attempt.error_type = error_type
    attempt.error_message = error_message
    attempt.updated_at = utcnow()
    await session.flush()


async def ensure_summary_state(session: AsyncSession, group: GroupChat) -> SummaryState:
    state = await session.scalar(select(SummaryState).where(SummaryState.group_id == group.id))
    if state:
        return state
    state = SummaryState(group=group, chat_id=group.chat_id, last_summary_sequence=0)
    session.add(state)
    await session.flush()
    return state


async def messages_after_sequence(
    session: AsyncSession,
    *,
    group: GroupChat,
    sequence: int,
) -> Sequence[GroupMessage]:
    result = await session.scalars(
        select(GroupMessage)
        .where(GroupMessage.group_id == group.id, GroupMessage.id > sequence)
        .order_by(GroupMessage.id)
    )
    return result.all()


async def latest_group_messages(
    session: AsyncSession,
    *,
    group: GroupChat,
    limit: int,
) -> Sequence[GroupMessage]:
    result = await session.scalars(
        select(GroupMessage)
        .where(GroupMessage.group_id == group.id)
        .order_by(GroupMessage.id.desc())
        .limit(limit)
    )
    return list(reversed(result.all()))


async def create_running_summary_job(
    session: AsyncSession,
    *,
    group: GroupChat,
    trigger_type: str,
    starting_sequence: int,
    lease_seconds: int = 300,
    prompt_version: str | None = None,
) -> SummaryJob | None:
    now = utcnow()
    active = await session.scalar(
        select(SummaryJob).where(
            SummaryJob.group_id == group.id,
            SummaryJob.status.in_(ACTIVE_SUMMARY_JOB_STATUSES),
        )
    )
    if active:
        if active.status == "running" and active.lease_expires_at and active.lease_expires_at <= now:
            active.status = "failed"
            active.error_type = "lease_expired"
            active.error_message = "stale running summary job was expired before starting a new job"
            active.finished_at = now
        else:
            return None

    job = SummaryJob(
        group=group,
        chat_id=group.chat_id,
        trigger_type=trigger_type,
        status="running",
        starting_sequence=starting_sequence,
        prompt_version=prompt_version,
        lease_expires_at=now + timedelta(seconds=lease_seconds),
        started_at=now,
    )
    session.add(job)
    await session.flush()
    return job


async def get_active_summary_job(
    session: AsyncSession,
    *,
    group_id: int,
) -> SummaryJob | None:
    return await session.scalar(
        select(SummaryJob)
        .options(selectinload(SummaryJob.result))
        .where(
            SummaryJob.group_id == group_id,
            SummaryJob.status.in_(ACTIVE_SUMMARY_JOB_STATUSES),
        )
        .order_by(SummaryJob.id.desc())
        .limit(1)
    )


async def create_pending_manual_summary_job(
    session: AsyncSession,
    *,
    group: GroupChat,
    starting_sequence: int,
    prompt_version: str | None = None,
) -> SummaryJob | None:
    if await get_active_summary_job(session, group_id=group.id) is not None:
        return None

    job = SummaryJob(
        group=group,
        chat_id=group.chat_id,
        trigger_type="manual",
        status="pending",
        starting_sequence=starting_sequence,
        prompt_version=prompt_version,
    )
    session.add(job)
    await session.flush()
    return job


async def mark_summary_job_running(
    session: AsyncSession,
    job: SummaryJob,
    *,
    lease_seconds: int = 300,
) -> bool:
    if job.status != "pending":
        return False
    now = utcnow()
    job.status = "running"
    job.started_at = now
    job.lease_expires_at = now + timedelta(seconds=lease_seconds)
    await session.flush()
    return True


async def finish_summary_job(
    session: AsyncSession,
    job: SummaryJob,
    status: str,
    *,
    cutoff_sequence: int | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    job.status = status
    job.cutoff_sequence = cutoff_sequence
    job.error_type = error_type
    job.error_message = error_message
    job.finished_at = utcnow()
    job.lease_expires_at = None
    await session.flush()


async def advance_summary_cursor_if_current(
    session: AsyncSession,
    *,
    state: SummaryState,
    expected_sequence: int,
    new_sequence: int,
) -> bool:
    result = await session.execute(
        update(SummaryState)
        .where(SummaryState.id == state.id)
        .where(SummaryState.last_summary_sequence == expected_sequence)
        .values(last_summary_sequence=new_sequence, last_summary_at=utcnow(), updated_at=utcnow())
    )
    await session.flush()
    return bool(result.rowcount)


async def create_summary_result(
    session: AsyncSession,
    *,
    job: SummaryJob,
    group: GroupChat,
    summary_text: str,
    delivered_admin_chat_id: int | None,
    delivered_message_id: int | None,
    prompt_version: str,
    interval_start_sequence: int,
    interval_end_sequence: int,
    llm_provider_id: int | None = None,
    summary_profile_id: int | None = None,
    model: str | None = None,
) -> SummaryResult:
    result = SummaryResult(
        job=job,
        group_id=group.id,
        summary_text=summary_text,
        delivered_admin_chat_id=delivered_admin_chat_id,
        delivered_message_id=delivered_message_id,
        prompt_version=prompt_version,
        llm_provider_id=llm_provider_id,
        summary_profile_id=summary_profile_id,
        model=model,
        interval_start_sequence=interval_start_sequence,
        interval_end_sequence=interval_end_sequence,
    )
    session.add(result)
    await session.flush()
    return result


async def create_summary_delivery_attempt(
    session: AsyncSession,
    *,
    summary_result: SummaryResult,
    relay_bot_id: int | None,
    target_chat_id: int | None,
    max_attempts: int,
    timeout_seconds: int,
    total_chunks: int,
    status: str = "pending",
    error_type: str | None = None,
    error_message: str | None = None,
) -> SummaryDeliveryAttempt:
    attempt = SummaryDeliveryAttempt(
        result=summary_result,
        relay_bot_id=relay_bot_id,
        target_chat_id=target_chat_id,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        total_chunks=total_chunks,
        status=status,
        error_type=error_type,
        error_message=error_message,
    )
    session.add(attempt)
    await session.flush()
    return attempt


async def update_summary_delivery_attempt(
    session: AsyncSession,
    attempt: SummaryDeliveryAttempt,
    *,
    status: str,
    attempt_count: int | None = None,
    sent_chunks: int | None = None,
    telegram_message_ids: list[int] | None = None,
    error_type: str | None = None,
    error_message: str | None = None,
    started: bool = False,
    finished: bool = False,
) -> None:
    now = utcnow()
    attempt.status = status
    if attempt_count is not None:
        attempt.attempt_count = attempt_count
    if sent_chunks is not None:
        attempt.sent_chunks = sent_chunks
    if telegram_message_ids is not None:
        attempt.telegram_message_ids = telegram_message_ids
    attempt.error_type = error_type
    attempt.error_message = error_message
    attempt.updated_at = now
    if started and attempt.started_at is None:
        attempt.started_at = now
    if finished:
        attempt.finished_at = now
    await session.flush()


async def latest_summary_delivery_attempt(
    session: AsyncSession,
    *,
    summary_result_id: int,
) -> SummaryDeliveryAttempt | None:
    return await session.scalar(
        select(SummaryDeliveryAttempt)
        .where(SummaryDeliveryAttempt.summary_result_id == summary_result_id)
        .order_by(SummaryDeliveryAttempt.id.desc())
        .limit(1)
    )


async def get_summary_job_for_group(
    session: AsyncSession,
    *,
    group_id: int,
    job_id: int,
) -> SummaryJob | None:
    return await session.scalar(
        select(SummaryJob)
        .options(selectinload(SummaryJob.result))
        .where(SummaryJob.group_id == group_id, SummaryJob.id == job_id)
    )


async def recent_summary_jobs_for_group(
    session: AsyncSession,
    *,
    group_id: int,
    limit: int = 10,
) -> Sequence[SummaryJob]:
    result = await session.scalars(
        select(SummaryJob)
        .options(selectinload(SummaryJob.result))
        .where(SummaryJob.group_id == group_id)
        .order_by(SummaryJob.id.desc())
        .limit(limit)
    )
    return result.all()
