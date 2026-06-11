from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Mapping, NoReturn

from aiogram import Bot, Dispatcher
from fastapi import FastAPI
import uvicorn
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig, BootstrapConfig, ConfigError
from summary_relay_bot.db.session import create_engine, create_session_factory
from summary_relay_bot.handlers import register_routers
from summary_relay_bot.scheduler import BotScheduler
from summary_relay_bot.services.runtime_config import BotRuntimeConfig, load_bot_runtime_config
from summary_relay_bot.services.secrets import SecretError, SecretService
from summary_relay_bot.telegram.bot import create_bot, ensure_polling_delivery
from summary_relay_bot.telegram.commands import setup_command_menus
from summary_relay_bot.web.app import create_web_app

logger = logging.getLogger(__name__)


LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"

TELEGRAM_STARTUP_READY = "ready"
TELEGRAM_STARTUP_NO_ENABLED_BOT = "no_enabled_bot"
TELEGRAM_STARTUP_BOT_SECRET_ERROR = "bot_secret_error"


@dataclass(slots=True)
class AppResources:
    config: AppConfig
    bot_runtime_config: BotRuntimeConfig | None
    owner_id: int
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
    web_app: FastAPI = field(repr=False)
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
    owner_id: int,
    bot_runtime_config: BotRuntimeConfig | None = None,
    bot: Bot | None = None,
    engine: AsyncEngine | None = None,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
    secret_service: SecretService,
) -> AppResources:
    if bot is None:
        if bot_runtime_config is None:
            raise ConfigError("bot runtime config is required to create bot")
        bot = create_bot(bot_runtime_config)
    dispatcher = Dispatcher()
    engine = engine or create_engine(config.database_url)
    session_factory = session_factory or create_session_factory(engine)
    scheduler = BotScheduler(
        config=config,
        bot=bot,
        session_factory=session_factory,
        secret_service=secret_service,
        owner_id=owner_id,
    )

    dispatcher["config"] = config
    dispatcher["owner_id"] = owner_id
    dispatcher["session_factory"] = session_factory
    dispatcher["scheduler"] = scheduler
    dispatcher["secret_service"] = secret_service
    register_routers(dispatcher, config, owner_id=owner_id)

    return AppResources(
        config=config,
        bot_runtime_config=bot_runtime_config,
        owner_id=owner_id,
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
        web_app = create_web_app(
            bootstrap_config=bootstrap_config,
            session_factory=session_factory,
            secret_service=secret_service,
            telegram_startup=telegram_startup.safe_dict(),
        )
        if not telegram_startup.should_start_polling:
            return RuntimeApp(
                bootstrap_config=bootstrap_config,
                telegram_startup=telegram_startup,
                engine=engine,
                session_factory=session_factory,
                web_app=web_app,
            )

        bot_runtime_config = telegram_startup.bot_runtime_config
        if bot_runtime_config is None:
            raise RuntimeError("telegram startup state is ready without bot runtime config")
        app_config = AppConfig.from_bootstrap_runtime(
            bootstrap_config,
            env=env,
        )
        resources = await build_app(
            app_config,
            owner_id=bot_runtime_config.owner_id,
            bot_runtime_config=bot_runtime_config,
            bot=create_bot(bot_runtime_config),
            engine=engine,
            session_factory=session_factory,
            secret_service=secret_service,
        )
        return RuntimeApp(
            bootstrap_config=bootstrap_config,
            telegram_startup=telegram_startup,
            engine=engine,
            session_factory=session_factory,
            web_app=web_app,
            resources=resources,
        )
    except Exception:
        await engine.dispose()
        raise


async def start_polling(resources: AppResources) -> None:
    try:
        await ensure_polling_delivery(resources.bot, resources.config)
        await setup_command_menus(resources.bot, resources.owner_id)
        await resources.scheduler.start()
        await resources.dispatcher.start_polling(resources.bot)
    finally:
        await resources.scheduler.stop()
        await resources.bot.session.close()
        await resources.engine.dispose()


async def start_web_api(runtime_app: RuntimeApp) -> None:
    config = uvicorn.Config(
        runtime_app.web_app,
        host=runtime_app.bootstrap_config.webui_host,
        port=runtime_app.bootstrap_config.webui_port,
        log_level="info",
        log_config=None,
    )
    server = uvicorn.Server(config)
    await server.serve()


async def run_runtime_app(runtime_app: RuntimeApp) -> None:
    if runtime_app.resources is None:
        try:
            await start_web_api(runtime_app)
        finally:
            await runtime_app.engine.dispose()
        return

    web_task = asyncio.create_task(start_web_api(runtime_app), name="web-api")
    polling_task = asyncio.create_task(start_polling(runtime_app.resources), name="telegram-polling")
    tasks = {web_task, polling_task}
    try:
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
        for task in done:
            task.result()
    finally:
        unfinished = [task for task in tasks if not task.done()]
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.gather(*unfinished, return_exceptions=True)
        await runtime_app.engine.dispose()


async def amain() -> None:
    configure_logging()
    try:
        bootstrap_config = BootstrapConfig.from_env(os.environ)
        runtime_app = await build_runtime_app(bootstrap_config, env=os.environ)
    except (ConfigError, SecretError) as exc:
        raise SystemExit(f"Configuration error: {exc}") from exc

    logger.info("Starting Summary Relay Bot with bootstrap config: %s", bootstrap_config.safe_dict())
    logger.info("Telegram polling startup state: %s", runtime_app.telegram_startup.safe_dict())
    await run_runtime_app(runtime_app)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format=LOG_FORMAT,
        datefmt=LOG_DATE_FORMAT,
        force=True,
    )


def main() -> NoReturn:
    asyncio.run(amain())
    raise SystemExit(0)


if __name__ == "__main__":
    main()
