from __future__ import annotations

import logging
from dataclasses import dataclass, field

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.group_settings import enabled_group_settings
from summary_relay_bot.services.retention import cleanup_raw_update_payloads
from summary_relay_bot.services.secrets import SecretService

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class BotScheduler:
    config: AppConfig
    bot: Bot
    session_factory: async_sessionmaker[AsyncSession]
    secret_service: SecretService
    owner_id: int
    scheduler: AsyncIOScheduler = field(init=False)

    def __post_init__(self) -> None:
        self.scheduler = AsyncIOScheduler(timezone=self.config.scheduler_timezone)

    async def start(self) -> None:
        async with session_scope(self.session_factory) as session:
            settings = list(await enabled_group_settings(session))

        target_job_ids = {f"summary:{setting.group.chat_id}" for setting in settings}
        for job in self.scheduler.get_jobs():
            if job.id.startswith("summary:") and job.id not in target_job_ids:
                self.scheduler.remove_job(job.id)

        for setting in settings:
            self.upsert_summary_job(setting.group.chat_id, setting.interval_minutes)
        self.upsert_retention_job()
        if not self.scheduler.running:
            self.scheduler.start()

    async def stop(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)

    def upsert_summary_job(self, chat_id: int, interval_minutes: int) -> None:
        from summary_relay_bot.services.summary_jobs import run_scheduled_summary

        self.scheduler.add_job(
            run_scheduled_summary,
            trigger="interval",
            minutes=interval_minutes,
            id=f"summary:{chat_id}",
            replace_existing=True,
            coalesce=self.config.scheduler_coalesce,
            misfire_grace_time=self.config.scheduler_misfire_grace_seconds,
            max_instances=1,
            kwargs={
                "bot": self.bot,
                "session_factory": self.session_factory,
                "secret_service": self.secret_service,
                "owner_id": self.owner_id,
                "chat_id": chat_id,
            },
        )

    def remove_summary_job(self, chat_id: int) -> None:
        job_id = f"summary:{chat_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    def upsert_retention_job(self) -> None:
        self.scheduler.add_job(
            run_retention_cleanup,
            trigger="interval",
            days=1,
            id="retention:raw_updates",
            replace_existing=True,
            coalesce=True,
            misfire_grace_time=self.config.scheduler_misfire_grace_seconds,
            max_instances=1,
            kwargs={
                "session_factory": self.session_factory,
                "retention_days": self.config.raw_update_retention_days,
            },
        )


async def run_retention_cleanup(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    retention_days: int,
) -> None:
    async with session_scope(session_factory) as session:
        result = await cleanup_raw_update_payloads(session, retention_days=retention_days)
    logger.info("Raw update retention cleanup redacted %s payloads", result.redacted_raw_updates)
