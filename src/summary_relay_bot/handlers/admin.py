from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import Message

from summary_relay_bot.telegram.guards import OwnerPrivateFilter, PrivateNonOwnerFilter, is_owner_user

ADMIN_HELP = (
    "Admin commands:\n"
    "/start - show bot status\n"
    "/help - show this help\n"
    "/reply <user_id> <message> - send a text reply to a known private user"
)

USER_HELP = (
    "Just send your message here. It will be forwarded to the bot owner, "
    "and they can reply through this bot."
)

USER_UNSUPPORTED_COMMAND = "Only /start and /help are available here."


def build_router(*, owner_id: int) -> Router:
    router = Router(name="admin")
    owner_private = OwnerPrivateFilter(owner_id)

    router.message.register(handle_admin_start, Command("start"), owner_private)
    router.message.register(handle_admin_help, Command("help"), owner_private)
    router.message.register(
        handle_non_owner_admin_command,
        Command("reply"),
        PrivateNonOwnerFilter(owner_id),
    )
    router.message.register(handle_user_help, Command("start", "help"), PrivateNonOwnerFilter(owner_id))
    router.message.register(handle_user_unsupported_command, PrivateNonOwnerFilter(owner_id), F.text.startswith("/"))
    return router


async def handle_admin_start(message: Message) -> None:
    await message.answer("Summary Relay Bot is running. Use /help for admin commands.")


async def handle_admin_help(message: Message) -> None:
    await message.answer(ADMIN_HELP)


async def handle_user_help(message: Message, owner_id: int) -> None:
    if is_owner_user(getattr(getattr(message, "from_user", None), "id", None), owner_id):
        return
    await message.answer(USER_HELP)


async def handle_user_unsupported_command(message: Message, owner_id: int) -> None:
    if is_owner_user(getattr(getattr(message, "from_user", None), "id", None), owner_id):
        return
    await message.answer(USER_UNSUPPORTED_COMMAND)


async def handle_non_owner_admin_command(message: Message, owner_id: int) -> None:
    user_id = getattr(getattr(message, "from_user", None), "id", None)
    chat_type = getattr(getattr(message, "chat", None), "type", None)
    if is_owner_user(user_id, owner_id):
        if chat_type != "private":
            return
        return
    if chat_type == "private":
        await message.answer("That command is only available to the bot owner.")
