from __future__ import annotations

from aiogram import Dispatcher

from summary_relay_bot.config import AppConfig
from summary_relay_bot.handlers import admin, admin_replies, private_user


def register_routers(dispatcher: Dispatcher, config: AppConfig, *, owner_id: int) -> None:
    dispatcher.include_router(admin.build_router(owner_id=owner_id))
    dispatcher.include_router(admin_replies.build_router(owner_id=owner_id))
    dispatcher.include_router(private_user.build_router(owner_id=owner_id))
