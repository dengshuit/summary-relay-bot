from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from typing import NoReturn

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig, ConfigError
from summary_relay_bot.db.session import create_engine, create_session_factory
from summary_relay_bot.handlers import register_routers
from summary_relay_bot.scheduler import BotScheduler
from summary_relay_bot.telegram.bot import create_bot, ensure_polling_delivery
from summary_relay_bot.telegram.commands import setup_command_menus

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AppResources:
    config: AppConfig
    bot: Bot
    dispatcher: Dispatcher
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    scheduler: BotScheduler


async def build_app(config: AppConfig) -> AppResources:
    bot = create_bot(config)
    dispatcher = Dispatcher()
    engine = create_engine(config.database_url)
    session_factory = create_session_factory(engine)
    scheduler = BotScheduler(config=config, bot=bot, session_factory=session_factory)

    dispatcher["config"] = config
    dispatcher["session_factory"] = session_factory
    dispatcher["scheduler"] = scheduler
    register_routers(dispatcher, config)

    return AppResources(
        config=config,
        bot=bot,
        dispatcher=dispatcher,
        engine=engine,
        session_factory=session_factory,
        scheduler=scheduler,
    )


async def start_polling(resources: AppResources) -> None:
    await ensure_polling_delivery(resources.bot, resources.config)
    await setup_command_menus(resources.bot, resources.config.owner_id)
    await resources.scheduler.start()
    try:
        await resources.dispatcher.start_polling(resources.bot)
    finally:
        await resources.scheduler.stop()
        await resources.bot.session.close()
        await resources.engine.dispose()


async def amain() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        config = AppConfig.from_env(os.environ)
    except ConfigError as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    resources = await build_app(config)
    logger.info("Starting Summary Relay Bot with config: %s", config.safe_dict())
    await start_polling(resources)


def main() -> NoReturn:
    asyncio.run(amain())
    raise SystemExit(0)


if __name__ == "__main__":
    main()
