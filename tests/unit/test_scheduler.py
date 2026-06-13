from __future__ import annotations

from summary_relay_bot.db.models import SummaryEntity
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.db.repositories import upsert_group
from summary_relay_bot.scheduler import BotScheduler
from summary_relay_bot.services.group_settings import enable_group_summary
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.runtime_config import set_group_summary_settings
from summary_relay_bot.services.userbot_auth import create_summary_userbot, update_summary_userbot


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
        assert f"summary:{enabled.id}" in job_ids
        assert "summary:-999" not in job_ids
        assert "retention:raw_updates" in job_ids
    finally:
        await scheduler.stop()


async def test_scheduler_only_uses_enabled_userbot_groups(app_config, session_factory) -> None:
    secret_service = SecretService(SecretService.generate_key())
    async with session_scope(session_factory) as session:
        old_userbot = await create_summary_userbot(
            session,
            secret_service=secret_service,
            name="Old userbot",
            api_id=12345,
            api_hash="old-api-hash-secret",
            phone_number="+15550001111",
            session_string="old-session-secret",
            enabled=True,
        )
        old_group = SummaryEntity(
            userbot_id=old_userbot.id,
            chat_id=-100,
            chat_type="megagroup",
            title="Old",
            enabled=True,
            collection_status="active",
            interval_minutes=15,
        )
        session.add(old_group)
        await session.flush()
        new_userbot = await create_summary_userbot(
            session,
            secret_service=secret_service,
            name="Enabled userbot",
            api_id=12346,
            api_hash="enabled-api-hash-secret",
            phone_number="+15550002222",
            session_string="enabled-session-secret",
            enabled=False,
        )
        new_group = SummaryEntity(
            userbot_id=new_userbot.id,
            chat_id=-100,
            chat_type="megagroup",
            title="New",
            enabled=True,
            collection_status="active",
            interval_minutes=20,
        )
        session.add(new_group)
        await session.flush()
        await update_summary_userbot(
            session,
            secret_service=secret_service,
            userbot_id=new_userbot.id,
            enabled=True,
        )
        await set_group_summary_settings(
            session,
            group=new_group,
            enabled=True,
            interval_minutes=20,
        )
        old_group_id = old_group.id
        new_group_id = new_group.id

    scheduler = BotScheduler(
        config=app_config,
        bot=FakeBot(),
        session_factory=session_factory,
        secret_service=secret_service,
        owner_id=1001,
    )
    try:
        await scheduler.start()

        job_ids = {job.id for job in scheduler.scheduler.get_jobs()}
        assert f"summary:{new_group_id}" in job_ids
        assert f"summary:{old_group_id}" not in job_ids
    finally:
        await scheduler.stop()
