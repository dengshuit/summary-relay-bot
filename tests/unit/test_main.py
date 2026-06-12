from __future__ import annotations

import asyncio
import logging
from types import SimpleNamespace

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.base import Base
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.main import (
    LOG_DATE_FORMAT,
    LOG_FORMAT,
    TELEGRAM_STARTUP_BOT_SECRET_ERROR,
    TELEGRAM_STARTUP_NO_ENABLED_BOT,
    TELEGRAM_STARTUP_READY,
    build_runtime_app,
    configure_logging,
    load_telegram_startup_state,
    run_runtime_app,
    start_polling,
)
from summary_relay_bot.services.runtime_config import create_bot_instance
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.summary_jobs import SummaryReloadGate
from summary_relay_bot.services.telegram_runtime import (
    TELEGRAM_RUNTIME_NO_ENABLED_BOT,
    TELEGRAM_RUNTIME_RUNNING,
    RuntimeBusyError,
    TelegramRuntimeManager,
)


class FakeTelegramSession:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeBot:
    def __init__(self) -> None:
        self.session = FakeTelegramSession()


class FakeScheduler:
    def __init__(self) -> None:
        self.started = False
        self.stopped = False

    async def start(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True


class FakeDispatcher:
    def __init__(self) -> None:
        self.started_with = None

    async def start_polling(self, bot: FakeBot) -> None:
        self.started_with = bot


class FakeEngine:
    def __init__(self) -> None:
        self.disposed = False

    async def dispose(self) -> None:
        self.disposed = True


async def _create_sqlite_database(path) -> str:
    database_url = f"sqlite+aiosqlite:///{path}"
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await engine.dispose()
    return database_url


async def _session_factory(database_url: str) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    return engine, async_sessionmaker(engine, expire_on_commit=False, autoflush=False)


def test_configure_logging_adds_timestamped_application_format() -> None:
    root_logger = logging.getLogger()
    original_handlers = root_logger.handlers[:]
    original_level = root_logger.level
    try:
        configure_logging()

        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) == 1
        formatter = root_logger.handlers[0].formatter
        assert formatter is not None
        assert formatter._fmt == LOG_FORMAT
        assert formatter.datefmt == LOG_DATE_FORMAT
    finally:
        root_logger.handlers[:] = original_handlers
        root_logger.setLevel(original_level)


async def test_load_telegram_startup_state_without_enabled_bot_skips_polling(session_factory) -> None:
    state = await load_telegram_startup_state(
        session_factory,
        secret_service=SecretService(SecretService.generate_key()),
    )

    assert state.status == TELEGRAM_STARTUP_NO_ENABLED_BOT
    assert state.bot_runtime_config is None
    assert state.should_start_polling is False


async def test_load_telegram_startup_state_decrypts_enabled_bot_and_redacts_runtime_state(
    tmp_path,
    caplog,
) -> None:
    service = SecretService(SecretService.generate_key())
    engine, factory = await _session_factory(f"sqlite+aiosqlite:///{tmp_path / 'enabled.db'}")
    try:
        async with session_scope(factory) as session:
            await create_bot_instance(
                session,
                secret_service=service,
                name="Main bot",
                bot_token="123456:runtime-secret-token",
                owner_id=3003,
                enabled=True,
            )

        state = await load_telegram_startup_state(factory, secret_service=service)
    finally:
        await engine.dispose()

    assert state.status == TELEGRAM_STARTUP_READY
    assert state.should_start_polling is True
    assert state.bot_runtime_config is not None
    assert state.bot_runtime_config.bot_token == "123456:runtime-secret-token"
    assert state.bot_runtime_config.owner_id == 3003
    assert "runtime-secret-token" not in repr(state)
    assert "3003" not in repr(state)

    logger = logging.getLogger("tests.unit.test_main")
    with caplog.at_level(logging.INFO, logger=logger.name):
        logger.info("telegram startup state: %s", state.safe_dict())
    assert "runtime-secret-token" not in caplog.text
    assert "3003" not in caplog.text


async def test_load_telegram_startup_state_reports_secret_failure_without_leaking_secret(tmp_path) -> None:
    writer_service = SecretService(SecretService.generate_key())
    reader_service = SecretService(SecretService.generate_key())
    engine, factory = await _session_factory(f"sqlite+aiosqlite:///{tmp_path / 'wrong-key.db'}")
    try:
        async with session_scope(factory) as session:
            await create_bot_instance(
                session,
                secret_service=writer_service,
                name="Main bot",
                bot_token="123456:runtime-secret-token",
                owner_id=3003,
                enabled=True,
            )

        state = await load_telegram_startup_state(factory, secret_service=reader_service)
    finally:
        await engine.dispose()

    assert state.status == TELEGRAM_STARTUP_BOT_SECRET_ERROR
    assert state.should_start_polling is False
    assert state.bot_runtime_config is None
    assert "runtime-secret-token" not in str(state)
    assert "runtime-secret-token" not in str(state.safe_dict())


async def test_build_runtime_app_without_enabled_bot_keeps_polling_resources_unbuilt(tmp_path) -> None:
    bootstrap_config = BootstrapConfig(
        database_url=await _create_sqlite_database(tmp_path / "empty.db"),
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token="admin-secret",
    )

    runtime_app = await build_runtime_app(bootstrap_config, env={})
    try:
        assert runtime_app.telegram_startup.status == TELEGRAM_STARTUP_NO_ENABLED_BOT
        assert runtime_app.telegram_startup.should_start_polling is False
        assert runtime_app.telegram_runtime.resources is None
        assert runtime_app.safe_dict()["polling_resources_ready"] is False
        assert "admin-secret" not in str(runtime_app.safe_dict())
    finally:
        await runtime_app.engine.dispose()


async def test_run_runtime_app_without_polling_starts_web_api_and_disposes_engine(monkeypatch) -> None:
    observed: dict[str, object] = {}
    engine = FakeEngine()
    telegram_runtime = SimpleNamespace(
        start_from_db=lambda: _record_async(observed, "started", True),
        stop=lambda: _record_async(observed, "stopped", True),
    )
    runtime_app = SimpleNamespace(
        engine=engine,
        telegram_runtime=telegram_runtime,
    )

    async def fake_start_web_api(observed_runtime_app) -> None:
        observed["web_runtime_app"] = observed_runtime_app

    monkeypatch.setattr("summary_relay_bot.main.start_web_api", fake_start_web_api)

    await run_runtime_app(runtime_app)

    assert observed["web_runtime_app"] is runtime_app
    assert observed["started"] is True
    assert observed["stopped"] is True
    assert engine.disposed is True


async def test_run_runtime_app_starts_manager_then_web_api(monkeypatch) -> None:
    observed: dict[str, object] = {}
    engine = FakeEngine()
    start_complete = asyncio.Event()

    async def fake_start_runtime() -> None:
        observed["runtime_started_before_web"] = "web_runtime_app" not in observed
        start_complete.set()

    async def fake_stop_runtime() -> None:
        observed["runtime_stopped"] = True

    runtime_app = SimpleNamespace(
        engine=engine,
        telegram_runtime=SimpleNamespace(
            start_from_db=fake_start_runtime,
            stop=fake_stop_runtime,
        ),
    )

    async def fake_start_web_api(observed_runtime_app) -> None:
        await start_complete.wait()
        observed["web_runtime_app"] = observed_runtime_app

    monkeypatch.setattr("summary_relay_bot.main.start_web_api", fake_start_web_api)

    await run_runtime_app(runtime_app)

    assert observed["web_runtime_app"] is runtime_app
    assert observed["runtime_started_before_web"] is True
    assert observed["runtime_stopped"] is True
    assert engine.disposed is True


async def test_build_runtime_app_uses_database_token_and_owner_for_bot_and_handlers(
    tmp_path,
    monkeypatch,
) -> None:
    encryption_key = SecretService.generate_key()
    service = SecretService(encryption_key)
    database_url = await _create_sqlite_database(tmp_path / "enabled-runtime.db")
    engine, factory = await _session_factory(database_url)
    async with session_scope(factory) as session:
        await create_bot_instance(
            session,
            secret_service=service,
            name="Main bot",
            bot_token="123456:AA-runtime-secret-token",
            owner_id=3003,
            enabled=True,
        )
    await engine.dispose()

    observed: dict[str, object] = {}

    def fake_create_bot(config, *, telegram_api_proxy=None):
        observed["bot_token"] = config.bot_token
        observed["owner_id_for_bot"] = config.owner_id
        observed["telegram_api_proxy"] = telegram_api_proxy
        return FakeBot()

    def fake_register_routers(dispatcher, config, *, owner_id: int) -> None:
        observed["owner_id_for_handlers"] = owner_id

    async def fake_start_polling(resources, *, ready_event=None) -> None:
        observed["polling_owner_id"] = resources.owner_id
        if ready_event is not None:
            ready_event.set()
        await asyncio.Event().wait()

    monkeypatch.setattr("summary_relay_bot.main.create_bot", fake_create_bot)
    monkeypatch.setattr("summary_relay_bot.main.register_routers", fake_register_routers)
    monkeypatch.setattr("summary_relay_bot.main.start_polling", fake_start_polling)

    bootstrap_config = BootstrapConfig(
        database_url=database_url,
        settings_encryption_key=encryption_key,
        webui_admin_token="admin-secret",
    )
    runtime_app = await build_runtime_app(bootstrap_config, env={})
    try:
        assert runtime_app.telegram_startup.status == TELEGRAM_STARTUP_READY
        await runtime_app.telegram_runtime.start_from_db()
        assert observed == {
            "bot_token": "123456:AA-runtime-secret-token",
            "owner_id_for_bot": 3003,
            "telegram_api_proxy": None,
            "owner_id_for_handlers": 3003,
            "polling_owner_id": 3003,
        }
        assert runtime_app.telegram_runtime.resources is not None
        assert runtime_app.telegram_runtime.resources.owner_id == 3003
        assert runtime_app.telegram_runtime.resources.bot_runtime_config is not None
        assert (
            runtime_app.telegram_runtime.resources.bot_runtime_config.bot_token
            == "123456:AA-runtime-secret-token"
        )
        assert runtime_app.telegram_runtime.state_snapshot().status == TELEGRAM_RUNTIME_RUNNING
    finally:
        await runtime_app.telegram_runtime.stop()
        await runtime_app.engine.dispose()


async def test_build_runtime_app_passes_telegram_api_proxy_to_bot_factory(
    tmp_path,
    monkeypatch,
) -> None:
    encryption_key = SecretService.generate_key()
    service = SecretService(encryption_key)
    database_url = await _create_sqlite_database(tmp_path / "enabled-runtime-proxy.db")
    engine, factory = await _session_factory(database_url)
    async with session_scope(factory) as session:
        await create_bot_instance(
            session,
            secret_service=service,
            name="Main bot",
            bot_token="123456:AA-runtime-secret-token",
            owner_id=3003,
            enabled=True,
        )
    await engine.dispose()

    observed: dict[str, object] = {}

    def fake_create_bot(config, *, telegram_api_proxy=None):
        observed["bot_token"] = config.bot_token
        observed["telegram_api_proxy"] = telegram_api_proxy
        return FakeBot()

    def fake_register_routers(dispatcher, config, *, owner_id: int) -> None:
        observed["owner_id_for_handlers"] = owner_id

    async def fake_start_polling(resources, *, ready_event=None) -> None:
        if ready_event is not None:
            ready_event.set()
        await asyncio.Event().wait()

    monkeypatch.setattr("summary_relay_bot.main.create_bot", fake_create_bot)
    monkeypatch.setattr("summary_relay_bot.main.register_routers", fake_register_routers)
    monkeypatch.setattr("summary_relay_bot.main.start_polling", fake_start_polling)

    bootstrap_config = BootstrapConfig(
        database_url=database_url,
        settings_encryption_key=encryption_key,
        webui_admin_token="admin-secret",
    )
    runtime_app = await build_runtime_app(
        bootstrap_config,
        env={"TELEGRAM_API_PROXY": "socks5://127.0.0.1:7890"},
    )
    try:
        await runtime_app.telegram_runtime.start_from_db()
        assert observed == {
            "bot_token": "123456:AA-runtime-secret-token",
            "telegram_api_proxy": "socks5://127.0.0.1:7890",
            "owner_id_for_handlers": 3003,
        }
    finally:
        await runtime_app.telegram_runtime.stop()
        await runtime_app.engine.dispose()


async def test_start_polling_uses_runtime_owner_id_for_command_menu(monkeypatch) -> None:
    observed: dict[str, object] = {}
    bot = FakeBot()
    dispatcher = FakeDispatcher()
    scheduler = FakeScheduler()
    engine = FakeEngine()
    resources = SimpleNamespace(
        bot=bot,
        config=SimpleNamespace(),
        owner_id=3003,
        scheduler=scheduler,
        dispatcher=dispatcher,
        engine=engine,
    )

    async def fake_ensure_polling_delivery(observed_bot, observed_config) -> None:
        observed["preflight_bot"] = observed_bot

    async def fake_setup_command_menus(observed_bot, owner_id: int) -> None:
        observed["command_menu_bot"] = observed_bot
        observed["command_menu_owner_id"] = owner_id

    monkeypatch.setattr("summary_relay_bot.main.ensure_polling_delivery", fake_ensure_polling_delivery)
    monkeypatch.setattr("summary_relay_bot.main.setup_command_menus", fake_setup_command_menus)

    await start_polling(resources)

    assert observed["preflight_bot"] is bot
    assert observed["command_menu_bot"] is bot
    assert observed["command_menu_owner_id"] == 3003
    assert scheduler.started is True
    assert scheduler.stopped is True
    assert dispatcher.started_with is bot
    assert bot.session.closed is True
    assert engine.disposed is False


async def test_runtime_manager_start_from_db_without_enabled_bot_sets_dynamic_state(tmp_path) -> None:
    bootstrap_config = BootstrapConfig(
        database_url=await _create_sqlite_database(tmp_path / "manager-empty.db"),
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token="admin-secret",
    )
    runtime_app = await build_runtime_app(bootstrap_config, env={})
    try:
        await runtime_app.telegram_runtime.start_from_db()

        state = runtime_app.telegram_runtime.state_snapshot()
        assert state.status == TELEGRAM_RUNTIME_NO_ENABLED_BOT
        assert state.detail == "no enabled bot instance is configured"
        assert runtime_app.telegram_runtime.resources is None
    finally:
        await runtime_app.engine.dispose()


async def test_runtime_manager_rejects_reload_change_when_summary_active(tmp_path) -> None:
    bootstrap_config = BootstrapConfig(
        database_url=await _create_sqlite_database(tmp_path / "manager-busy.db"),
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token="admin-secret",
    )
    engine = create_async_engine(bootstrap_config.database_url)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    gate = SummaryReloadGate()
    manager = TelegramRuntimeManager(
        bootstrap_config=bootstrap_config,
        env={},
        engine=engine,
        session_factory=factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        reload_gate=gate,
        build_resources=lambda *args, **kwargs: _unexpected_call(),
        start_polling=lambda resources, **kwargs: _unexpected_call(),
    )
    called = False

    async def change(session):
        nonlocal called
        called = True
        return await _unexpected_call()

    try:
        async with gate.enter_bot_delivery_summary():
            try:
                await manager.reload_after_change(change)
            except RuntimeBusyError:
                pass
            else:
                raise AssertionError("expected RuntimeBusyError")

        assert called is False
    finally:
        await engine.dispose()


async def _record_async(observed: dict[str, object], key: str, value: object) -> None:
    observed[key] = value


async def _unexpected_call():
    raise AssertionError("unexpected call")
