from __future__ import annotations

from typing import Any

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.db.models import DeliveryAttempt, PrivateUser, TelegramUpdate
from summary_relay_bot.db.repositories import (
    create_delivery_attempt,
    create_private_message,
    create_reply_map,
    mark_delivery_attempt_status,
    mark_raw_update_status,
    upsert_private_user,
)
from summary_relay_bot.services.info_cards import render_private_text_relay, render_private_user_info_card
from summary_relay_bot.services.message_extraction import message_type_for_private_copy
from summary_relay_bot.telegram.errors import classify_telegram_error


async def relay_private_message(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    raw_update: TelegramUpdate,
    message: Any,
) -> None:
    user = getattr(message, "from_user", None)
    if user is None:
        await mark_raw_update_status(session, raw_update, "failed", error_type="missing_user")
        return

    source_chat_id = int(getattr(getattr(message, "chat", None), "id"))
    source_message_id = int(getattr(message, "message_id"))
    private_user = await upsert_private_user(
        session,
        telegram_user_id=int(getattr(user, "id")),
        username=getattr(user, "username", None),
        first_name=getattr(user, "first_name", None),
        last_name=getattr(user, "last_name", None),
        language_code=getattr(user, "language_code", None),
    )
    message_type = message_type_for_private_copy(message)
    inbound = await create_private_message(
        session,
        private_user=private_user,
        raw_update=raw_update,
        direction="incoming",
        telegram_chat_id=source_chat_id,
        telegram_message_id=source_message_id,
        message_type=message_type,
        text=getattr(message, "text", None),
        caption=getattr(message, "caption", None),
        delivery_status="stored",
    )

    if message_type == "text":
        await _relay_private_text_message(
            session=session,
            bot=bot,
            owner_id=owner_id,
            raw_update=raw_update,
            private_user=private_user,
            inbound=inbound,
            user=user,
            source_message_id=source_message_id,
            text=getattr(message, "text", "") or "",
        )
        return

    await _relay_private_copied_message(
        session=session,
        bot=bot,
        owner_id=owner_id,
        raw_update=raw_update,
        private_user=private_user,
        inbound=inbound,
        user=user,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
    )


async def _relay_private_text_message(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    raw_update: TelegramUpdate,
    private_user: PrivateUser,
    inbound: Any,
    user: Any,
    source_message_id: int,
    text: str,
) -> None:
    try:
        delivered = await bot.send_message(
            owner_id,
            render_private_text_relay(user, text),
            parse_mode="HTML",
        )
    except Exception as exc:
        failure = classify_telegram_error(exc)
        inbound.delivery_status = "failed" if failure.retryable else "blocked"
        inbound.error_type = failure.error_type
        inbound.error_message = failure.message
        await create_delivery_attempt(
            session,
            purpose="private_text_message",
            target_chat_id=owner_id,
            source_message_id=source_message_id,
            status="failed",
            error_type=failure.error_type,
            error_message=failure.message,
        )
        await mark_raw_update_status(
            session,
            raw_update,
            "failed",
            error_type=failure.error_type,
            error_message="private relay text delivery failed",
        )
        return

    delivered_message_id = getattr(delivered, "message_id", None)
    inbound.admin_message_id = delivered_message_id
    text_attempt = await create_delivery_attempt(
        session,
        purpose="private_text_message",
        target_chat_id=owner_id,
        source_message_id=source_message_id,
        result_message_id=delivered_message_id,
        status="sent",
    )
    if delivered_message_id is None:
        inbound.delivery_status = "partial_failed"
        inbound.error_type = "missing_delivered_message_id"
        inbound.error_message = "sendMessage returned no message_id"
        await mark_delivery_attempt_status(
            session,
            text_attempt,
            "failed",
            error_type="missing_delivered_message_id",
            error_message="sendMessage returned no message_id",
        )
        await _notify_admin(
            bot,
            owner_id,
            f"The relayed user message could not be mapped safely. Use /reply {private_user.telegram_user_id} <message>.",
        )
        await mark_raw_update_status(
            session,
            raw_update,
            "private_relay_partial",
            error_type=inbound.error_type,
            error_message=inbound.error_message,
        )
        return

    mapped = await _create_reply_map_or_warn(
        session=session,
        bot=bot,
        owner_id=owner_id,
        private_user=private_user,
        private_message=inbound,
        attempt=text_attempt,
        admin_message_id=int(delivered_message_id),
        source_kind="text_message",
    )
    if not mapped:
        inbound.delivery_status = "partial_failed"
        inbound.error_type = "reply_mapping_failed"
        inbound.error_message = "relayed text reply mapping failed"
        await mark_raw_update_status(
            session,
            raw_update,
            "private_relay_partial",
            error_type=inbound.error_type,
            error_message=inbound.error_message,
        )
        return

    inbound.delivery_status = "sent"
    await mark_raw_update_status(session, raw_update, "private_relayed")


async def _relay_private_copied_message(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    raw_update: TelegramUpdate,
    private_user: PrivateUser,
    inbound: Any,
    user: Any,
    source_chat_id: int,
    source_message_id: int,
) -> None:
    try:
        copied = await bot.copy_message(
            chat_id=owner_id,
            from_chat_id=source_chat_id,
            message_id=source_message_id,
        )
    except Exception as exc:
        failure = classify_telegram_error(exc)
        inbound.delivery_status = "failed" if failure.retryable else "blocked"
        inbound.error_type = failure.error_type
        inbound.error_message = failure.message
        await create_delivery_attempt(
            session,
            purpose="private_copy_message",
            target_chat_id=owner_id,
            source_chat_id=source_chat_id,
            source_message_id=source_message_id,
            status="failed",
            error_type=failure.error_type,
            error_message=failure.message,
        )
        await _notify_admin(
            bot,
            owner_id,
            f"Could not copy the user's message. Use /reply {private_user.telegram_user_id} <message>.",
        )
        await mark_raw_update_status(
            session,
            raw_update,
            "failed",
            error_type=failure.error_type,
            error_message="private relay copyMessage failed",
        )
        return

    copied_message_id = getattr(copied, "message_id", None)
    inbound.admin_message_id = copied_message_id
    copy_attempt = await create_delivery_attempt(
        session,
        purpose="private_copy_message",
        target_chat_id=owner_id,
        source_chat_id=source_chat_id,
        source_message_id=source_message_id,
        result_message_id=copied_message_id,
        status="sent",
    )
    partial_failure = False
    if copied_message_id is None:
        partial_failure = True
        inbound.error_type = "missing_copied_message_id"
        inbound.error_message = "copyMessage returned no message_id"
        await mark_delivery_attempt_status(
            session,
            copy_attempt,
            "failed",
            error_type="missing_copied_message_id",
            error_message="copyMessage returned no message_id",
        )
        await _notify_admin(
            bot,
            owner_id,
            "The copied user message could not be mapped safely. Use /reply <user_id> <message>.",
        )
    else:
        copy_mapped = await _create_reply_map_or_warn(
            session=session,
            bot=bot,
            owner_id=owner_id,
            private_user=private_user,
            private_message=inbound,
            attempt=copy_attempt,
            admin_message_id=int(copied_message_id),
            source_kind="copied_message",
        )
        partial_failure = partial_failure or not copy_mapped
        if not copy_mapped:
            inbound.error_type = "reply_mapping_failed"
            inbound.error_message = "copied message reply mapping failed"

    context_mapped = await _send_context_card_for_copied_message(
        session=session,
        bot=bot,
        owner_id=owner_id,
        private_user=private_user,
        private_message=inbound,
        user=user,
        source_message_id=source_message_id,
        copied_message_id=copied_message_id,
    )
    partial_failure = partial_failure or not context_mapped
    if not context_mapped and inbound.error_type is None:
        inbound.error_type = "reply_mapping_failed"
        inbound.error_message = "context card reply mapping failed"

    if partial_failure:
        inbound.delivery_status = "partial_failed"
        await mark_raw_update_status(
            session,
            raw_update,
            "private_relay_partial",
            error_type=inbound.error_type,
            error_message=inbound.error_message,
        )
    else:
        inbound.delivery_status = "sent"
        await mark_raw_update_status(session, raw_update, "private_relayed")


async def _send_context_card_for_copied_message(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    private_user: PrivateUser,
    private_message: Any,
    user: Any,
    source_message_id: int,
    copied_message_id: int | None,
) -> bool:
    try:
        info_card = await bot.send_message(
            owner_id,
            render_private_user_info_card(user, source_message_id),
            reply_to_message_id=copied_message_id,
        )
    except Exception as exc:
        failure = classify_telegram_error(exc)
        await create_delivery_attempt(
            session,
            purpose="private_context_card",
            target_chat_id=owner_id,
            source_message_id=source_message_id,
            status="failed",
            error_type=failure.error_type,
            error_message=failure.message,
        )
        return False

    info_message_id = getattr(info_card, "message_id", None)
    info_attempt = await create_delivery_attempt(
        session,
        purpose="private_context_card",
        target_chat_id=owner_id,
        source_message_id=source_message_id,
        result_message_id=info_message_id,
        status="sent",
    )
    if info_message_id is None:
        await mark_delivery_attempt_status(
            session,
            info_attempt,
            "failed",
            error_type="missing_context_message_id",
            error_message="context card sendMessage returned no message_id",
        )
        return False

    return await _create_reply_map_or_warn(
        session=session,
        bot=bot,
        owner_id=owner_id,
        private_user=private_user,
        private_message=private_message,
        attempt=info_attempt,
        admin_message_id=int(info_message_id),
        source_kind="context_card",
    )


async def _create_reply_map_or_warn(
    *,
    session: AsyncSession,
    bot: Bot,
    owner_id: int,
    private_user: PrivateUser,
    private_message: Any,
    attempt: DeliveryAttempt,
    admin_message_id: int,
    source_kind: str,
) -> bool:
    try:
        async with session.begin_nested():
            await create_reply_map(
                session,
                private_user=private_user,
                private_message=private_message,
                admin_chat_id=owner_id,
                admin_message_id=admin_message_id,
                source_kind=source_kind,
            )
    except Exception as exc:
        await mark_delivery_attempt_status(
            session,
            attempt,
            "failed",
            error_type=exc.__class__.__name__,
            error_message="reply map persistence failed",
        )
        await _notify_admin(
            bot,
            owner_id,
            f"Could not create a safe reply mapping for the {source_kind.replace('_', ' ')}. "
            f"Use /reply {private_user.telegram_user_id} <message> for this user.",
        )
        return False

    await mark_delivery_attempt_status(session, attempt, "mapped")
    return True


async def _notify_admin(bot: Bot, owner_id: int, text: str) -> None:
    try:
        await bot.send_message(owner_id, text)
    except Exception:
        pass
