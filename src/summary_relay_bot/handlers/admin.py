from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.summary_jobs import run_manual_summary
from summary_relay_bot.telegram.guards import OwnerPrivateFilter, PrivateNonOwnerFilter, is_owner_user

ADMIN_HELP = (
    "Admin commands:\n"
    "/groups - list discovered groups\n"
    "/summary [chat_id] - summarize enabled groups or one group\n"
    "/enable_group <chat_id> [minutes] - enable scheduled summaries\n"
    "/disable_group <chat_id> - disable scheduled summaries\n"
    "/set_interval <chat_id> <minutes> - update a group's interval\n"
    "/reply <user_id> <message> - send a text reply to a known private user"
)

USER_HELP = (
    "Send a private message here and it will be relayed to the bot owner. "
    "The owner can reply through the bot without exposing their personal account."
)


def build_router(config: AppConfig) -> Router:
    router = Router(name="admin")
    owner_private = OwnerPrivateFilter(config.owner_id)

    router.message.register(handle_admin_start, Command("start"), owner_private)
    router.message.register(handle_admin_help, Command("help"), owner_private)
    router.message.register(handle_manual_summary, Command("summary"), owner_private)
    router.message.register(
        handle_non_owner_admin_command,
        Command("summary", "groups", "enable_group", "disable_group", "set_interval", "reply"),
        PrivateNonOwnerFilter(config.owner_id),
    )
    router.message.register(handle_user_help, Command("help"), PrivateNonOwnerFilter(config.owner_id))
    return router


async def handle_admin_start(message: Message) -> None:
    await message.answer("Summary Relay Bot is running. Use /help for admin commands.")


async def handle_admin_help(message: Message) -> None:
    await message.answer(ADMIN_HELP)


async def handle_user_help(message: Message, config: AppConfig) -> None:
    if is_owner_user(getattr(getattr(message, "from_user", None), "id", None), config.owner_id):
        return
    await message.answer(USER_HELP)


async def handle_non_owner_admin_command(message: Message, config: AppConfig) -> None:
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    chat_type = getattr(getattr(message, "chat", None), "type", None)
    if is_owner_user(user_id, config.owner_id):
        if chat_type != "private":
            return
        return
    if chat_type == "private":
        await message.answer("That command is only available to the bot owner.")


async def handle_manual_summary(
    message: Message,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    text = getattr(message, "text", "") or ""
    parts = text.split(maxsplit=1)
    try:
        chat_id = int(parts[1]) if len(parts) > 1 else None
    except ValueError:
        await message.answer("Usage: /summary [chat_id]")
        return
    async with session_scope(session_factory) as session:
        report = await run_manual_summary(
            session=session,
            bot=message.bot,
            config=config,
            requested_chat_id=chat_id,
        )
    await message.answer(report)
