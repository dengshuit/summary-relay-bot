from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.admin_replies import AdminReplyError, route_admin_reply, send_reply_command
from summary_relay_bot.telegram.guards import OwnerPrivateFilter


def build_router(config: AppConfig) -> Router:
    router = Router(name="admin_replies")
    owner_private = OwnerPrivateFilter(config.owner_id)
    router.message.register(handle_reply_command, Command("reply"), owner_private)
    router.message.register(handle_admin_reply, owner_private, F.reply_to_message)
    router.message.register(handle_unscoped_admin_message, owner_private)
    return router


async def handle_reply_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = getattr(message, "text", "") or ""
    parts = text.split(maxsplit=2)
    if len(parts) != 3:
        await message.answer("Usage: /reply <user_id> <message>")
        return
    try:
        user_id = int(parts[1])
        async with session_scope(session_factory) as session:
            result = await send_reply_command(
                session=session,
                bot=message.bot,
                user_id=user_id,
                text=parts[2],
            )
        await message.answer(result)
    except (ValueError, AdminReplyError) as exc:
        await message.answer(str(exc))


async def handle_admin_reply(
    message: Message,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    try:
        async with session_scope(session_factory) as session:
            result = await route_admin_reply(
                session=session,
                bot=message.bot,
                config=config,
                message=message,
            )
        await message.answer(result)
    except AdminReplyError as exc:
        await message.answer(str(exc))


async def handle_unscoped_admin_message(message: Message) -> None:
    if getattr(message, "text", "") and str(message.text).startswith("/"):
        return
    await message.answer("Reply to a mapped user message or use /reply <user_id> <message>.")
