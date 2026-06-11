from __future__ import annotations

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.db.repositories import upsert_group
from summary_relay_bot.scheduler import BotScheduler
from summary_relay_bot.services.group_settings import enable_group_summary
from summary_relay_bot.services.secrets import SecretService


class FakeBot:
    pass


async def test_scheduler_rebuilds_enabled_groups_and_removes_stale_summary_jobs(app_config, session_factory) -> None:
    async with session_scope(session_factory) as session:
        enabled = await upsert_group(session, chat_id=-100, chat_type="group", title="Enabled")
        await enable_group_summary(
            session=session,
            chat_id=enabled.chat_id,
            interval_minutes=15,
        )
        await upsert_group(session, chat_id=-200, chat_type="group", title="Disabled")

    scheduler = BotScheduler(
        config=app_config,
        bot=FakeBot(),
        session_factory=session_factory,
        secret_service=SecretService(SecretService.generate_key()),
        owner_id=1001,
    )
    scheduler.upsert_summary_job(-999, 10)
    try:
        await scheduler.start()

        job_ids = {job.id for job in scheduler.scheduler.get_jobs()}
        assert "summary:-100" in job_ids
        assert "summary:-200" not in job_ids
        assert "summary:-999" not in job_ids
        assert "retention:raw_updates" in job_ids
    finally:
        await scheduler.stop()
