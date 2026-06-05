from __future__ import annotations

from aiogram import Dispatcher

from summary_relay_bot.config import AppConfig
from summary_relay_bot.handlers import admin, admin_groups, admin_replies, group, private_user


def register_routers(dispatcher: Dispatcher, config: AppConfig) -> None:
    dispatcher.include_router(admin.build_router(config))
    dispatcher.include_router(admin_groups.build_router(config))
    dispatcher.include_router(admin_replies.build_router(config))
    dispatcher.include_router(private_user.build_router(config))
    dispatcher.include_router(group.build_router(config))
