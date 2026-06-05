from __future__ import annotations

from summary_relay_bot.db.repositories import upsert_group
from summary_relay_bot.services.group_settings import update_group_summary_interval


async def test_discovered_group_has_no_schedule_interval_until_configured(db_session) -> None:
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")

    assert group.summaries_enabled is False
    assert group.summary_interval_minutes is None


async def test_set_interval_does_not_enable_disabled_group(db_session) -> None:
    group = await upsert_group(db_session, chat_id=-200, chat_type="supergroup", title="Group")

    updated = await update_group_summary_interval(db_session, chat_id=group.chat_id, interval_minutes=45)

    assert updated.summary_interval_minutes == 45
    assert updated.summaries_enabled is False
