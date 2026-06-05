from __future__ import annotations

import logging

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import (
    BotCommand,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
)

logger = logging.getLogger(__name__)

ADMIN_COMMANDS = [
    BotCommand(command="start", description="Show bot status"),
    BotCommand(command="help", description="Show administrator help"),
    BotCommand(command="groups", description="List known groups"),
    BotCommand(command="summary", description="Summarize enabled groups or one chat"),
    BotCommand(command="enable_group", description="Enable scheduled summaries for a group"),
    BotCommand(command="disable_group", description="Disable scheduled summaries for a group"),
    BotCommand(command="set_interval", description="Set group summary interval"),
    BotCommand(command="reply", description="Reply to a known private user"),
]

USER_COMMANDS = [
    BotCommand(command="start", description="Start the bot"),
    BotCommand(command="help", description="Show help"),
]


async def setup_command_menus(bot: Bot, owner_id: int) -> None:
    try:
        await bot.set_my_commands(USER_COMMANDS, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(ADMIN_COMMANDS, scope=BotCommandScopeChat(chat_id=owner_id))
        await bot.set_my_commands([], scope=BotCommandScopeAllGroupChats())
    except TelegramAPIError as exc:
        logger.warning("Telegram command menu setup failed: %s", exc.__class__.__name__)
