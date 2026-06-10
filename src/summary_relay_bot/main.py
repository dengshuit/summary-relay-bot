from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Mapping, NoReturn

from aiogram import Bot, Dispatcher
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig, BootstrapConfig, ConfigError
from summary_relay_bot.db.session import create_engine, create_session_factory
from summary_relay_bot.handlers import register_routers
from summary_relay_bot.scheduler import BotScheduler
from summary_relay_bot.services.runtime_config import BotRuntimeConfig, load_bot_runtime_config
from summary_relay_bot.services.secrets import SecretError, SecretService
from summary_relay_bot.telegram.bot import create_bot, ensure_polling_delivery
from summary_relay_bot.telegram.commands import setup_command_menus

logger = logging.getLogger(__name__)


TELEGRAM_STARTUP_READY = "ready"
TELEGRAM_STARTUP_NO_ENABLED_BOT = "no_enabled_bot"
TELEGRAM_STARTUP_BOT_SECRET_ERROR = "bot_secret_error"


@dataclass(slots=True)
class AppResources:
    config: AppConfig
    bot_runtime_config: BotRuntimeConfig | None
    bot: Bot = field(repr=False)
    dispatcher: Dispatcher = field(repr=False)
    engine: AsyncEngine = field(repr=False)
    session_factory: async_sessionmaker[AsyncSession] = field(repr=False)
    scheduler: BotScheduler = field(repr=False)


@dataclass(frozen=True, slots=True)
class TelegramStartupState:
    status: str
    bot_runtime_config: BotRuntimeConfig | None = None
    detail: str | None = None

    @property
    def should_start_polling(self) -> bool:
        return self.status == TELEGRAM_STARTUP_READY

    def safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "bot_runtime_config": (
                self.bot_runtime_config.safe_dict() if self.bot_runtime_config is not None else None
            ),
            "detail": self.detail,
        }

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"TelegramStartupState({args})"


@dataclass(slots=True)
class RuntimeApp:
    bootstrap_config: BootstrapConfig
    telegram_startup: TelegramStartupState
    engine: AsyncEngine = field(repr=False)
    session_factory: async_sessionmaker[AsyncSession] = field(repr=False)
    resources: AppResources | None = field(default=None, repr=False)

    def safe_dict(self) -> dict[str, object]:
        return {
            "bootstrap_config": self.bootstrap_config.safe_dict(),
            "telegram_startup": self.telegram_startup.safe_dict(),
            "polling_resources_ready": self.resources is not None,
        }

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"RuntimeApp({args})"


async def load_telegram_startup_state(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    secret_service: SecretService,
) -> TelegramStartupState:
    async with session_factory() as session:
        try:
            bot_runtime_config = await load_bot_runtime_config(
                session,
                secret_service=secret_service,
            )
        except SecretError:
            return TelegramStartupState(
                status=TELEGRAM_STARTUP_BOT_SECRET_ERROR,
                detail="enabled bot token could not be decrypted",
            )

    if bot_runtime_config is None:
        return TelegramStartupState(
            status=TELEGRAM_STARTUP_NO_ENABLED_BOT,
            detail="no enabled bot instance is configured",
        )
    return TelegramStartupState(
        status=TELEGRAM_STARTUP_READY,
        bot_runtime_config=bot_runtime_config,
        detail="enabled bot instance loaded",
    )


async def build_app(
    config: AppConfig,
    *,
    bot_runtime_config: BotRuntimeConfig | None = None,
    bot: Bot | None = None,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> AppResources:
    bot = bot or create_bot(config)
    dispatcher = Dispatcher()
    engine = engine or create_engine(config.database_url)
    session_factory = session_factory or create_session_factory(engine)
    scheduler = BotScheduler(config=config, bot=bot, session_factory=session_factory)

    dispatcher["config"] = config
    dispatcher["session_factory"] = session_factory
    dispatcher["scheduler"] = scheduler
    register_routers(dispatcher, config)

    return AppResources(
        config=config,
        bot_runtime_config=bot_runtime_config,
        bot=bot,
        dispatcher=dispatcher,
        engine=engine,
        session_factory=session_factory,
        scheduler=scheduler,
    )


async def build_runtime_app(
    bootstrap_config: BootstrapConfig,
    *,
    env: Mapping[str, str],
) -> RuntimeApp:
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    engine = create_engine(bootstrap_config.database_url)
    session_factory = create_session_factory(engine)

    try:
        telegram_startup = await load_telegram_startup_state(
            session_factory,
            secret_service=secret_service,
        )
        if not telegram_startup.should_start_polling:
            return RuntimeApp(
                bootstrap_config=bootstrap_config,
                telegram_startup=telegram_startup,
                engine=engine,
                session_factory=session_factory,
            )

        bot_runtime_config = telegram_startup.bot_runtime_config
        if bot_runtime_config is None:
            raise RuntimeError("telegram startup state is ready without bot runtime config")
        app_config = AppConfig.from_bootstrap_runtime(
            bootstrap_config,
            bot_token=bot_runtime_config.bot_token,
            owner_id=bot_runtime_config.owner_id,
            env=env,
        )
        resources = await build_app(
            app_config,
            bot_runtime_config=bot_runtime_config,
            bot=create_bot(bot_runtime_config),
            engine=engine,
            session_factory=session_factory,
        )
        return RuntimeApp(
            bootstrap_config=bootstrap_config,
            telegram_startup=telegram_startup,
            engine=engine,
            session_factory=session_factory,
            resources=resources,
        )
    except Exception:
        await engine.dispose()
        raise


async def start_polling(resources: AppResources) -> None:
    try:
        await ensure_polling_delivery(resources.bot, resources.config)
        await setup_command_menus(resources.bot, resources.config.owner_id)
        await resources.scheduler.start()
        await resources.dispatcher.start_polling(resources.bot)
    finally:
        await resources.scheduler.stop()
        await resources.bot.session.close()
        await resources.engine.dispose()


async def amain() -> None:
    logging.basicConfig(level=logging.INFO)
    try:
        bootstrap_config = BootstrapConfig.from_env(os.environ)
        runtime_app = await build_runtime_app(bootstrap_config, env=os.environ)
    except (ConfigError, SecretError) as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    logger.info("Starting Summary Relay Bot with bootstrap config: %s", bootstrap_config.safe_dict())
    logger.info("Telegram polling startup state: %s", runtime_app.telegram_startup.safe_dict())
    if runtime_app.resources is None:
        await runtime_app.engine.dispose()
        return

    await start_polling(runtime_app.resources)


def main() -> NoReturn:
    asyncio.run(amain())
    raise SystemExit(0)


if __name__ == "__main__":
    main()
