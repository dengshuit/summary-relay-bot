from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.models import SummaryUserbot, utcnow
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.userbot_auth import UserbotConfigError, UserbotRuntimeConfig, load_enabled_userbot_runtime_config
from summary_relay_bot.services.userbot_ingestion import (
    DeletedMessage,
    DialogDiscoveryProvider,
    EditedMessage,
    IncomingMessage,
    ingest_userbot_message,
    ingest_userbot_message_edit,
    mark_userbot_message_deleted,
    refresh_enabled_userbot_dialogs,
)
from summary_relay_bot.telegram.userbot import (
    UserbotClientConfig,
    UserbotUpdateCollector,
    UserbotUpdateCollectorFactory,
    UserbotUpdateHandlers,
    create_telethon_update_collector,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SummaryUserbotRuntimeManager:
    session_factory: async_sessionmaker[AsyncSession]
    secret_service: SecretService
    discover_dialogs: DialogDiscoveryProvider
    create_update_collector: UserbotUpdateCollectorFactory = create_telethon_update_collector
    _collector: UserbotUpdateCollector | None = field(default=None, init=False)
    _collector_task: asyncio.Task[None] | None = field(default=None, init=False)
    _collector_userbot_id: int | None = field(default=None, init=False)

    async def start_from_db(self) -> None:
        if self._collector_task is not None and not self._collector_task.done():
            return

        try:
            async with session_scope(self.session_factory) as session:
                runtime = await load_enabled_userbot_runtime_config(
                    session,
                    secret_service=self.secret_service,
                )
                if runtime is None:
                    return
                userbot = await session.get(SummaryUserbot, runtime.userbot_id)
                if userbot is None:
                    return
                userbot.runtime_status = "starting"
                userbot.last_error_type = None
                userbot.last_error_message = None
                userbot.updated_at = utcnow()

                await refresh_enabled_userbot_dialogs(
                    session,
                    secret_service=self.secret_service,
                    discover_dialogs=self.discover_dialogs,
                )
                userbot = await session.get(SummaryUserbot, runtime.userbot_id)
                if userbot is not None:
                    now = utcnow()
                    userbot.runtime_status = "running"
                    userbot.last_started_at = now
                    userbot.last_error_type = None
                    userbot.last_error_message = None
                    userbot.updated_at = now
            self._start_collector(runtime)
        except UserbotConfigError as exc:
            logger.warning("Summary userbot runtime configuration failed: %s", exc)
            await self._mark_enabled_userbot_failed("userbot_config_error", str(exc))
        except Exception as exc:
            logger.exception("Summary userbot startup discovery failed")
            await self._mark_enabled_userbot_failed(type(exc).__name__, "summary userbot startup discovery failed")

    async def stop(self) -> None:
        await self._stop_collector()
        async with session_scope(self.session_factory) as session:
            runtime = await load_enabled_userbot_runtime_config(
                session,
                secret_service=self.secret_service,
            )
            if runtime is None:
                return
            userbot = await session.get(SummaryUserbot, runtime.userbot_id)
            if userbot is None:
                return
            userbot.runtime_status = "stopped"
            userbot.last_stopped_at = utcnow()
            userbot.updated_at = utcnow()

    def _start_collector(self, runtime: UserbotRuntimeConfig) -> None:
        handlers = UserbotUpdateHandlers(
            on_message=self._ingest_message,
            on_edit=self._ingest_edit,
            on_delete=self._mark_deleted,
        )
        collector = self.create_update_collector(
            UserbotClientConfig(
                api_id=runtime.api_id,
                api_hash=runtime.api_hash,
                session_string=runtime.session_string,
                proxy_url=runtime.proxy_url,
            ),
            runtime.userbot_id,
            handlers,
        )
        self._collector = collector
        self._collector_userbot_id = runtime.userbot_id
        self._collector_task = asyncio.create_task(
            self._run_collector(runtime.userbot_id, collector),
            name=f"summary-userbot-{runtime.userbot_id}-collector",
        )

    async def _run_collector(self, userbot_id: int, collector: UserbotUpdateCollector) -> None:
        try:
            await collector.run_until_disconnected()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Summary userbot update collector failed")
            await self._mark_failed(userbot_id, type(exc).__name__, "summary userbot update collector failed")

    async def _stop_collector(self) -> None:
        collector = self._collector
        task = self._collector_task
        self._collector = None
        self._collector_task = None
        self._collector_userbot_id = None
        if collector is not None:
            await collector.disconnect()
        if task is None:
            return
        if not task.done():
            task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    async def _ingest_message(self, message: IncomingMessage) -> None:
        async with session_scope(self.session_factory) as session:
            await ingest_userbot_message(session, message)

    async def _ingest_edit(self, edit: EditedMessage) -> None:
        async with session_scope(self.session_factory) as session:
            await ingest_userbot_message_edit(session, edit)

    async def _mark_deleted(self, deleted: DeletedMessage) -> None:
        async with session_scope(self.session_factory) as session:
            await mark_userbot_message_deleted(session, deleted)

    async def _mark_failed(self, userbot_id: int, error_type: str, error_message: str) -> None:
        async with session_scope(self.session_factory) as session:
            userbot = await session.get(SummaryUserbot, userbot_id)
            if userbot is None:
                return
            userbot.runtime_status = "failed"
            userbot.last_error_type = error_type
            userbot.last_error_message = error_message
            userbot.updated_at = utcnow()

    async def _mark_enabled_userbot_failed(self, error_type: str, error_message: str) -> None:
        async with session_scope(self.session_factory) as session:
            userbot = await session.scalar(
                select(SummaryUserbot).where(SummaryUserbot.enabled.is_(True))
            )
            if userbot is None:
                return
            userbot.runtime_status = "failed"
            userbot.last_error_type = error_type
            userbot.last_error_message = error_message
            userbot.updated_at = utcnow()
