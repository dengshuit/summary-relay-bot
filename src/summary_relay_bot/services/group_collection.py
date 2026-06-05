from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.models import GroupMessage, TelegramUpdate
from summary_relay_bot.db.repositories import mark_raw_update_status, store_group_message, upsert_group
from summary_relay_bot.services.message_extraction import extract_message_for_summary
from summary_relay_bot.telegram.guards import is_group_chat


@dataclass(frozen=True, slots=True)
class GroupCollectionResult:
    stored: bool
    duplicate: bool
    status: str
    message: GroupMessage | None = None


def _display_name(user: Any) -> str | None:
    if user is None:
        return None
    parts = [getattr(user, "first_name", None), getattr(user, "last_name", None)]
    name = " ".join(part for part in parts if part)
    username = getattr(user, "username", None)
    if name and username:
        return f"{name} (@{username})"
    if name:
        return name
    if username:
        return f"@{username}"
    return None


async def collect_group_message(
    session: AsyncSession,
    *,
    config: AppConfig,
    raw_update: TelegramUpdate,
    message: Any,
) -> GroupCollectionResult:
    chat = getattr(message, "chat", None)
    chat_type = getattr(chat, "type", None)
    if not is_group_chat(chat_type):
        await mark_raw_update_status(session, raw_update, "ignored_non_group")
        return GroupCollectionResult(stored=False, duplicate=False, status="ignored_non_group")

    group = await upsert_group(
        session,
        chat_id=int(getattr(chat, "id")),
        chat_type=str(chat_type),
        title=getattr(chat, "title", None),
        username=getattr(chat, "username", None),
    )

    extracted = extract_message_for_summary(message)
    if extracted.unsupported:
        await mark_raw_update_status(
            session,
            raw_update,
            "ignored_unsupported",
            error_type=extracted.unsupported_reason,
            error_message=extracted.summary_content,
        )
        return GroupCollectionResult(stored=False, duplicate=False, status="ignored_unsupported")

    group_message, created = await store_group_message(
        session,
        group=group,
        raw_update=raw_update,
        telegram_message_id=int(getattr(message, "message_id")),
        sender_user_id=getattr(getattr(message, "from_user", None), "id", None),
        sender_display_name=_display_name(getattr(message, "from_user", None)),
        message_type=extracted.message_type,
        text=extracted.text,
        caption=extracted.caption,
        summary_content=extracted.summary_content,
        file_id=extracted.file_id,
        file_unique_id=extracted.file_unique_id,
        file_name=extracted.file_name,
        mime_type=extracted.mime_type,
        file_size=extracted.file_size,
        media_metadata=extracted.media_metadata,
    )
    await mark_raw_update_status(
        session,
        raw_update,
        "stored_for_summary" if created else "duplicate_update",
    )
    return GroupCollectionResult(
        stored=created,
        duplicate=not created,
        status="stored_for_summary" if created else "duplicate_update",
        message=group_message,
    )
