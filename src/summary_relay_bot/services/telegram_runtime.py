from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig, BootstrapConfig
from summary_relay_bot.db.models import utcnow
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    BotInstanceView,
    BotRuntimeConfig,
    clear_bot_restart_flags,
    get_bot_instance_view,
    load_bot_runtime_config,
    mark_bot_restart_flags,
    redact_owner_id,
)
from summary_relay_bot.services.secrets import SecretError, SecretService
from summary_relay_bot.services.summary_jobs import SummaryReloadGate

if TYPE_CHECKING:
    from summary_relay_bot.main import AppResources

logger = logging.getLogger(__name__)


TELEGRAM_RUNTIME_NO_ENABLED_BOT = "no_enabled_bot"
TELEGRAM_RUNTIME_STARTING = "starting"
TELEGRAM_RUNTIME_RUNNING = "running"
TELEGRAM_RUNTIME_RELOADING = "reloading"
TELEGRAM_RUNTIME_STOPPED = "stopped"
TELEGRAM_RUNTIME_FAILED = "failed"


class RuntimeBusyError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class TelegramRuntimeState:
    status: str
    detail: str | None = None
    bot_instance_id: int | None = None
    bot_name: str | None = None
    owner_id_redacted: str | None = None
    last_reload_at: datetime | None = None
    last_reload_error: str | None = None

    def safe_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "detail": self.detail,
            "bot_instance_id": self.bot_instance_id,
            "bot_name": self.bot_name,
            "owner_id_redacted": self.owner_id_redacted,
            "last_reload_at": self.last_reload_at.isoformat() if self.last_reload_at else None,
            "last_reload_error": self.last_reload_error,
        }


@dataclass(slots=True)
class TelegramRuntimeManager:
    bootstrap_config: BootstrapConfig
    env: Mapping[str, str]
    engine: AsyncEngine
    session_factory: async_sessionmaker[AsyncSession]
    secret_service: SecretService
    reload_gate: SummaryReloadGate
    build_resources: Callable[..., Awaitable["AppResources"]]
    start_polling: Callable[..., Awaitable[None]]
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False, repr=False)
    _resources: "AppResources | None" = field(default=None, init=False, repr=False)
    _polling_task: asyncio.Task[None] | None = field(default=None, init=False, repr=False)
    _state: TelegramRuntimeState = field(
        default_factory=lambda: TelegramRuntimeState(
            status=TELEGRAM_RUNTIME_STOPPED,
            detail="Telegram runtime has not started",
        ),
        init=False,
    )

    def state_snapshot(self) -> TelegramRuntimeState:
        return self._state

    @property
    def resources(self) -> "AppResources | None":
        return self._resources

    async def start_from_db(self) -> None:
        async with self._lock:
            try:
                await self._reload_locked()
            except Exception:
                logger.exception("Telegram runtime failed during startup")

    async def reload_from_db(self) -> None:
        async with self._lock:
            if not await self.reload_gate.try_begin_runtime_reload():
                raise RuntimeBusyError("Bot runtime reload is blocked by an active summary")
            try:
                await self._stop_locked(set_stopped_state=False)
                await self._reload_locked()
            finally:
                await self.reload_gate.finish_runtime_reload()

    async def reload_after_change(
        self,
        change: Callable[[AsyncSession], Awaitable[BotInstanceView]],
    ) -> BotInstanceView:
        async with self._lock:
            if not await self.reload_gate.try_begin_runtime_reload():
                raise RuntimeBusyError("Bot runtime reload is blocked by an active summary")

            try:
                affected_ids = self._affected_bot_instance_ids()
                await self._stop_locked(set_stopped_state=False)

                try:
                    async with session_scope(self.session_factory) as session:
                        bot = await change(session)
                        affected_ids.add(bot.id)
                        await mark_bot_restart_flags(session, bot_instance_ids=affected_ids)
                except Exception:
                    try:
                        await self._reload_locked()
                    except Exception:
                        logger.exception("Telegram runtime failed to resume after rejected config change")
                    raise

                try:
                    await self._reload_locked(clear_restart_ids=affected_ids)
                except Exception:
                    pass

                async with self.session_factory() as session:
                    return await get_bot_instance_view(session, bot.id)
            finally:
                await self.reload_gate.finish_runtime_reload()

    async def stop(self) -> None:
        async with self._lock:
            await self._stop_locked(set_stopped_state=True)

    async def _reload_locked(self, *, clear_restart_ids: set[int] | None = None) -> None:
        self._set_state(TELEGRAM_RUNTIME_STARTING, "starting Telegram runtime from database")
        try:
            async with session_scope(self.session_factory) as session:
                runtime_config = await load_bot_runtime_config(
                    session,
                    secret_service=self.secret_service,
                )
        except SecretError:
            self._set_state(
                TELEGRAM_RUNTIME_FAILED,
                "enabled bot token could not be decrypted",
                last_reload_error="secret_error",
            )
            raise

        if runtime_config is None:
            self._resources = None
            await self._clear_restart_flags(clear_restart_ids)
            self._set_state(
                TELEGRAM_RUNTIME_NO_ENABLED_BOT,
                "no enabled bot instance is configured",
            )
            return

        try:
            app_config = AppConfig.from_bootstrap_runtime(
                self.bootstrap_config,
                env=self.env,
            )
            resources = await self.build_resources(
                app_config,
                owner_id=runtime_config.owner_id,
                bot_runtime_config=runtime_config,
                bot=None,
                engine=self.engine,
                session_factory=self.session_factory,
                secret_service=self.secret_service,
                reload_gate=self.reload_gate,
            )
            await self._start_polling_task(resources)
            self._resources = resources
            await self._clear_restart_flags(clear_restart_ids)
            self._set_state(
                TELEGRAM_RUNTIME_RUNNING,
                "Telegram polling is running",
                bot_runtime_config=runtime_config,
            )
        except Exception as exc:
            self._resources = None
            self._set_state(
                TELEGRAM_RUNTIME_FAILED,
                "Telegram runtime failed to start",
                bot_runtime_config=runtime_config,
                last_reload_error=type(exc).__name__,
            )
            raise

    async def _start_polling_task(self, resources: "AppResources") -> None:
        ready_event = asyncio.Event()
        task = asyncio.create_task(
            self.start_polling(resources, ready_event=ready_event),
            name="telegram-polling",
        )
        self._polling_task = task
        task.add_done_callback(self._polling_done)
        ready_task = asyncio.create_task(ready_event.wait(), name="telegram-polling-ready")
        done, _pending = await asyncio.wait(
            {task, ready_task},
            return_when=asyncio.FIRST_COMPLETED,
        )
        if task in done:
            if not ready_task.done():
                ready_task.cancel()
                await asyncio.gather(ready_task, return_exceptions=True)
            task.result()
            raise RuntimeError("Telegram polling stopped during startup")
        if ready_task in done:
            return

    def _polling_done(self, task: asyncio.Task[None]) -> None:
        if self._polling_task is not task:
            return
        if task.cancelled():
            return
        try:
            task.result()
        except Exception as exc:
            logger.exception("Telegram polling stopped unexpectedly")
            runtime_config = self._resources.bot_runtime_config if self._resources is not None else None
            self._set_state(
                TELEGRAM_RUNTIME_FAILED,
                "Telegram polling stopped unexpectedly",
                bot_runtime_config=runtime_config,
                last_reload_error=type(exc).__name__,
            )
            return
        runtime_config = self._resources.bot_runtime_config if self._resources is not None else None
        self._set_state(
            TELEGRAM_RUNTIME_FAILED,
            "Telegram polling stopped unexpectedly",
            bot_runtime_config=runtime_config,
            last_reload_error="polling_stopped",
        )

    async def _stop_locked(self, *, set_stopped_state: bool) -> None:
        task = self._polling_task
        self._polling_task = None
        self._resources = None
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        if set_stopped_state:
            self._set_state(TELEGRAM_RUNTIME_STOPPED, "Telegram runtime is stopped")

    def _affected_bot_instance_ids(self) -> set[int]:
        if self._resources is None or self._resources.bot_runtime_config is None:
            return set()
        return {self._resources.bot_runtime_config.bot_instance_id}

    async def _clear_restart_flags(self, bot_instance_ids: set[int] | None) -> None:
        async with session_scope(self.session_factory) as session:
            await clear_bot_restart_flags(session, bot_instance_ids=bot_instance_ids)

    def _set_state(
        self,
        status: str,
        detail: str | None,
        *,
        bot_runtime_config: BotRuntimeConfig | None = None,
        last_reload_error: str | None = None,
    ) -> None:
        self._state = TelegramRuntimeState(
            status=status,
            detail=detail,
            bot_instance_id=(
                bot_runtime_config.bot_instance_id if bot_runtime_config is not None else None
            ),
            bot_name=bot_runtime_config.name if bot_runtime_config is not None else None,
            owner_id_redacted=(
                redact_owner_id(bot_runtime_config.owner_id)
                if bot_runtime_config is not None
                else None
            ),
            last_reload_at=utcnow(),
            last_reload_error=last_reload_error,
        )
