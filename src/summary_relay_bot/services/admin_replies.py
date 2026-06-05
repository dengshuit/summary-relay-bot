from __future__ import annotations

import asyncio
from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.repositories import (
    create_private_message,
    find_reply_map,
    get_private_user_by_telegram_id,
)
from summary_relay_bot.services.message_extraction import message_type_for_private_copy
from summary_relay_bot.telegram.errors import classify_telegram_error


class AdminReplyError(ValueError):
    pass


def _delivery_failure_message(error_type: str) -> str:
    if error_type == "telegram_forbidden":
        return "Could not deliver reply: the private user blocked the bot or cannot receive messages."
    if error_type in {"rate_limited", "telegram_transient"}:
        return "Could not deliver reply because Telegram returned a temporary delivery error."
    return "Could not deliver reply to the private user."


async def _find_reply_map_with_short_retry(
    session: AsyncSession,
    *,
    admin_chat_id: int,
    admin_message_id: int,
) -> Any | None:
    reply_map = await find_reply_map(
        session,
        admin_chat_id=admin_chat_id,
        admin_message_id=admin_message_id,
    )
    if reply_map is not None:
        return reply_map
    await asyncio.sleep(0.1)
    return await find_reply_map(
        session,
        admin_chat_id=admin_chat_id,
        admin_message_id=admin_message_id,
    )


async def route_admin_reply(
    *,
    session: AsyncSession,
    bot: Bot,
    config: AppConfig,
    message: Any,
) -> str:
    reply_to = getattr(message, "reply_to_message", None)
    if reply_to is None:
        raise AdminReplyError("Reply to a relayed user message or use /reply <user_id> <message>.")

    reply_map = await _find_reply_map_with_short_retry(
        session,
        admin_chat_id=config.owner_id,
        admin_message_id=int(getattr(reply_to, "message_id")),
    )
    if reply_map is None:
        raise AdminReplyError(
            "That message is not mapped to a private user yet. Try again in a moment or use /reply for known users."
        )
    if reply_map.status == "mapping_pending":
        raise AdminReplyError("Reply mapping is still being saved. Try again in a moment.")
    if reply_map.status != "mapped":
        raise AdminReplyError("That message is unsafe to reply to because mapping failed.")

    target_user = reply_map.private_user
    message_type = message_type_for_private_copy(message)
    text = getattr(message, "text", None)
    caption = getattr(message, "caption", None)

    try:
        if text is not None:
            delivered = await bot.send_message(target_user.telegram_user_id, text)
        else:
            delivered = await bot.copy_message(
                chat_id=target_user.telegram_user_id,
                from_chat_id=config.owner_id,
                message_id=int(getattr(message, "message_id")),
            )
    except Exception as exc:
        failure = classify_telegram_error(exc)
        await create_private_message(
            session,
            private_user=target_user,
            direction="outgoing",
            telegram_chat_id=target_user.telegram_user_id,
            telegram_message_id=getattr(message, "message_id", None),
            message_type=message_type,
            text=text,
            caption=caption,
            delivery_status="failed" if failure.retryable else "blocked",
            error_type=failure.error_type,
            error_message=failure.message,
        )
        raise AdminReplyError(_delivery_failure_message(failure.error_type)) from exc

    await create_private_message(
        session,
        private_user=target_user,
        direction="outgoing",
        telegram_chat_id=target_user.telegram_user_id,
        telegram_message_id=getattr(delivered, "message_id", None),
        message_type=message_type,
        text=text,
        caption=caption,
        delivery_status="sent",
    )
    return "Reply delivered."


async def send_reply_command(
    *,
    session: AsyncSession,
    bot: Bot,
    user_id: int,
    text: str,
) -> str:
    if not text.strip():
        raise AdminReplyError("Reply text cannot be empty.")
    target_user = await get_private_user_by_telegram_id(session, user_id)
    if target_user is None:
        raise AdminReplyError("That user is unknown. The bot must not initiate new private conversations.")
    try:
        delivered = await bot.send_message(user_id, text.strip())
    except Exception as exc:
        failure = classify_telegram_error(exc)
        await create_private_message(
            session,
            private_user=target_user,
            direction="outgoing",
            telegram_chat_id=user_id,
            message_type="text",
            text=text.strip(),
            delivery_status="failed" if failure.retryable else "blocked",
            error_type=failure.error_type,
            error_message=failure.message,
        )
        raise AdminReplyError(_delivery_failure_message(failure.error_type)) from exc

    await create_private_message(
        session,
        private_user=target_user,
        direction="outgoing",
        telegram_chat_id=user_id,
        telegram_message_id=getattr(delivered, "message_id", None),
        message_type="text",
        text=text.strip(),
        delivery_status="sent",
    )
    return "Reply delivered."
