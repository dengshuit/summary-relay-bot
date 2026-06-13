from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.db.models import SummaryEntity, SummaryMessage, SummaryState, SummaryUserbot, utcnow
from summary_relay_bot.db.repositories import ensure_summary_state
from summary_relay_bot.services.userbot_auth import (
    UserbotConfigError,
    load_enabled_userbot_runtime_config,
)
from summary_relay_bot.services.secrets import SecretService


SUPPORTED_COLLECTION_ENTITY_TYPES = frozenset({"group", "supergroup", "megagroup"})
IGNORED_DISCOVERY_ENTITY_TYPES = frozenset({"broadcast_channel", "channel"})


@dataclass(frozen=True, slots=True)
class DiscoveredDialog:
    telegram_entity_id: int
    entity_type: str
    title: str | None = None
    username: str | None = None
    telegram_access_hash: int | None = None
    telegram_peer_type: str | None = None


@dataclass(frozen=True, slots=True)
class IncomingMessage:
    userbot_id: int
    telegram_entity_id: int
    telegram_message_id: int
    message_date: datetime
    text: str | None = None
    caption: str | None = None
    message_type: str | None = None
    telegram_thread_id: int | None = None
    edited_at: datetime | None = None
    sender_user_id: int | None = None
    sender_username: str | None = None
    sender_display_name: str | None = None
    media_metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class EditedMessage:
    userbot_id: int
    telegram_entity_id: int
    telegram_message_id: int
    edited_at: datetime
    text: str | None = None
    caption: str | None = None
    message_type: str | None = None
    media_metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class DeletedMessage:
    userbot_id: int
    telegram_entity_id: int
    telegram_message_ids: Sequence[int]
    deleted_at: datetime


@dataclass(frozen=True, slots=True)
class DialogRefreshResult:
    discovered: int
    created: int
    updated: int
    ignored: int


@dataclass(frozen=True, slots=True)
class MessageIngestResult:
    status: str
    message_id: int | None = None
    created: bool = False


@dataclass(frozen=True, slots=True)
class EditIngestResult:
    status: str
    message_id: int | None = None


@dataclass(frozen=True, slots=True)
class DeleteIngestResult:
    marked: int
    missing: int


DialogDiscoveryProvider = Callable[[object], Awaitable[Sequence[DiscoveredDialog]]]


async def refresh_enabled_userbot_dialogs(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    discover_dialogs: DialogDiscoveryProvider,
) -> DialogRefreshResult:
    runtime = await load_enabled_userbot_runtime_config(session, secret_service=secret_service)
    if runtime is None:
        raise UserbotConfigError("enabled authorized userbot is required")
    userbot = await session.get(SummaryUserbot, runtime.userbot_id)
    if userbot is None:
        raise UserbotConfigError("enabled authorized userbot is required")
    dialogs = await discover_dialogs(runtime)
    return await refresh_userbot_dialogs(session, userbot=userbot, dialogs=dialogs)


async def refresh_userbot_dialogs(
    session: AsyncSession,
    *,
    userbot: SummaryUserbot,
    dialogs: Sequence[DiscoveredDialog],
) -> DialogRefreshResult:
    created = 0
    updated = 0
    ignored = 0
    now = utcnow()

    for dialog in dialogs:
        normalized_type = _normalize_entity_type(dialog.entity_type)
        if normalized_type not in SUPPORTED_COLLECTION_ENTITY_TYPES:
            ignored += 1
            continue
        existing = await _get_entity_by_telegram_id(
            session,
            userbot_id=userbot.id,
            telegram_entity_id=dialog.telegram_entity_id,
        )
        if existing is None:
            group = SummaryEntity(
                userbot_id=userbot.id,
                chat_id=dialog.telegram_entity_id,
                telegram_access_hash=dialog.telegram_access_hash,
                telegram_peer_type=dialog.telegram_peer_type or normalized_type,
                chat_type=normalized_type,
                title=dialog.title,
                username=dialog.username,
                enabled=False,
                collection_status="disabled",
                discovered_at=now,
                last_seen_at=now,
                last_refreshed_at=now,
            )
            session.add(group)
            await session.flush()
            await ensure_summary_state(session, group)
            created += 1
            continue

        before = _entity_snapshot(existing)
        existing.telegram_access_hash = dialog.telegram_access_hash
        existing.telegram_peer_type = dialog.telegram_peer_type or normalized_type
        existing.chat_type = normalized_type
        existing.title = dialog.title
        existing.username = dialog.username
        existing.last_seen_at = now
        existing.last_refreshed_at = now
        existing.updated_at = now
        if _entity_snapshot(existing) != before:
            updated += 1

    await session.flush()
    return DialogRefreshResult(
        discovered=created + updated,
        created=created,
        updated=updated,
        ignored=ignored,
    )


async def ingest_userbot_message(
    session: AsyncSession,
    message: IncomingMessage,
) -> MessageIngestResult:
    group = await _get_enabled_collectable_group(
        session,
        userbot_id=message.userbot_id,
        telegram_entity_id=message.telegram_entity_id,
    )
    if group is None:
        return MessageIngestResult(status="ignored_disabled_or_unknown")

    existing = await _get_message(
        session,
        group_id=group.id,
        telegram_message_id=message.telegram_message_id,
    )
    if existing is not None:
        return MessageIngestResult(status="deduped", message_id=existing.id, created=False)

    normalized = _normalize_message_content(
        text=message.text,
        caption=message.caption,
        message_type=message.message_type,
        media_metadata=message.media_metadata,
    )
    stored = SummaryMessage(
        group=group,
        userbot_id=message.userbot_id,
        telegram_message_id=message.telegram_message_id,
        telegram_thread_id=message.telegram_thread_id,
        source_kind="telethon_update",
        message_date=_as_aware_utc(message.message_date),
        edited_at=_as_aware_utc(message.edited_at) if message.edited_at is not None else None,
        sender_user_id=message.sender_user_id,
        sender_username=message.sender_username,
        sender_display_name=message.sender_display_name,
        message_type=normalized.message_type,
        text=normalized.text,
        caption=normalized.caption,
        summary_content=normalized.summary_content,
        media_metadata=normalized.media_metadata,
    )
    group.last_seen_at = utcnow()
    group.updated_at = utcnow()
    session.add(stored)
    await session.flush()
    return MessageIngestResult(status="stored", message_id=stored.id, created=True)


async def ingest_userbot_message_edit(
    session: AsyncSession,
    edit: EditedMessage,
) -> EditIngestResult:
    group = await _get_enabled_collectable_group(
        session,
        userbot_id=edit.userbot_id,
        telegram_entity_id=edit.telegram_entity_id,
    )
    if group is None:
        return EditIngestResult(status="ignored_disabled_or_unknown")

    message = await _get_message(
        session,
        group_id=group.id,
        telegram_message_id=edit.telegram_message_id,
    )
    if message is None:
        return EditIngestResult(status="missing")

    state = await ensure_summary_state(session, group)
    edit_time = _as_aware_utc(edit.edited_at)
    if message.id <= state.last_summary_sequence:
        message.edited_at = edit_time
        if message.edited_after_summary_at is None:
            message.edited_after_summary_at = edit_time
        await session.flush()
        return EditIngestResult(status="marked_after_summary", message_id=message.id)

    normalized = _normalize_message_content(
        text=edit.text,
        caption=edit.caption,
        message_type=edit.message_type,
        media_metadata=edit.media_metadata,
    )
    message.text = normalized.text
    message.caption = normalized.caption
    message.summary_content = normalized.summary_content
    message.message_type = normalized.message_type
    message.media_metadata = normalized.media_metadata
    message.edited_at = edit_time
    await session.flush()
    return EditIngestResult(status="updated", message_id=message.id)


async def mark_userbot_message_deleted(
    session: AsyncSession,
    deleted: DeletedMessage,
) -> DeleteIngestResult:
    group = await _get_entity_by_telegram_id(
        session,
        userbot_id=deleted.userbot_id,
        telegram_entity_id=deleted.telegram_entity_id,
    )
    if group is None:
        return DeleteIngestResult(marked=0, missing=len(deleted.telegram_message_ids))

    marked = 0
    missing = 0
    delete_time = _as_aware_utc(deleted.deleted_at)
    for telegram_message_id in deleted.telegram_message_ids:
        message = await _get_message(
            session,
            group_id=group.id,
            telegram_message_id=telegram_message_id,
        )
        if message is None:
            missing += 1
            continue
        message.deleted_at = delete_time
        marked += 1
    await session.flush()
    return DeleteIngestResult(marked=marked, missing=missing)


@dataclass(frozen=True, slots=True)
class _NormalizedContent:
    message_type: str
    text: str | None
    caption: str | None
    summary_content: str
    media_metadata: dict[str, object] | None = field(default=None)


def _normalize_message_content(
    *,
    text: str | None,
    caption: str | None,
    message_type: str | None,
    media_metadata: dict[str, object] | None,
) -> _NormalizedContent:
    normalized_text = _normalize_optional_text(text)
    normalized_caption = _normalize_optional_text(caption)
    media_kind = _normalize_optional_text(message_type)
    if media_kind is None:
        media_kind = "text" if normalized_text is not None and media_metadata is None else "media"
    if normalized_text is not None:
        summary_content = normalized_text
    elif normalized_caption is not None:
        summary_content = normalized_caption
    else:
        summary_content = f"[media: {media_kind}]"
    metadata = dict(media_metadata or {})
    return _NormalizedContent(
        message_type=media_kind,
        text=normalized_text,
        caption=normalized_caption,
        summary_content=summary_content,
        media_metadata=metadata or None,
    )


async def _get_enabled_collectable_group(
    session: AsyncSession,
    *,
    userbot_id: int,
    telegram_entity_id: int,
) -> SummaryEntity | None:
    group = await _get_entity_by_telegram_id(
        session,
        userbot_id=userbot_id,
        telegram_entity_id=telegram_entity_id,
    )
    if group is None:
        return None
    if not group.enabled or group.collection_status != "active":
        return None
    if group.chat_type not in SUPPORTED_COLLECTION_ENTITY_TYPES:
        return None
    return group


async def _get_entity_by_telegram_id(
    session: AsyncSession,
    *,
    userbot_id: int,
    telegram_entity_id: int,
) -> SummaryEntity | None:
    return await session.scalar(
        select(SummaryEntity).where(
            SummaryEntity.userbot_id == userbot_id,
            SummaryEntity.chat_id == telegram_entity_id,
        )
    )


async def _get_message(
    session: AsyncSession,
    *,
    group_id: int,
    telegram_message_id: int,
) -> SummaryMessage | None:
    return await session.scalar(
        select(SummaryMessage).where(
            SummaryMessage.group_id == group_id,
            SummaryMessage.telegram_message_id == telegram_message_id,
        )
    )


def _entity_snapshot(group: SummaryEntity) -> tuple[object, ...]:
    return (
        group.telegram_access_hash,
        group.telegram_peer_type,
        group.chat_type,
        group.title,
        group.username,
    )


def _normalize_entity_type(value: str) -> str:
    normalized = value.strip().lower()
    if normalized == "channel":
        return "broadcast_channel"
    return normalized


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)
