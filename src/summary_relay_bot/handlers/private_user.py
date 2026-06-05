from __future__ import annotations

from aiogram import Router
from aiogram.types import Message, Update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.private_relay import relay_private_message
from summary_relay_bot.services.update_ingest import persist_raw_update
from summary_relay_bot.telegram.guards import PrivateNonOwnerFilter


def build_router(config: AppConfig) -> Router:
    router = Router(name="private_user")
    router.message.register(handle_private_user_message, PrivateNonOwnerFilter(config.owner_id))
    return router


async def handle_private_user_message(
    message: Message,
    event_update: Update,
    config: AppConfig,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_scope(session_factory) as session:
        raw_update, created = await persist_raw_update(session, event_update)
        if not created:
            return
        await relay_private_message(
            session=session,
            bot=message.bot,
            config=config,
            raw_update=raw_update,
            message=message,
        )
