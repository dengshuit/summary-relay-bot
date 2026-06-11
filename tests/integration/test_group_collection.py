from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from summary_relay_bot.db.models import GroupChat, GroupSummarySettings
from summary_relay_bot.db.repositories import get_or_create_raw_update
from summary_relay_bot.services.group_collection import collect_group_message


async def test_group_collection_marks_unsupported_debuggable_without_schedule_defaults(
    app_config,
    db_session,
) -> None:
    raw_update, _ = await get_or_create_raw_update(
        db_session,
        update_id=801,
        payload={"update_id": 801},
    )
    message = SimpleNamespace(
        message_id=10,
        text=None,
        caption="mystery",
        chat=SimpleNamespace(id=-100, type="group", title="Group", username=None),
        from_user=SimpleNamespace(id=2002, first_name="Alice", last_name=None, username=None),
    )

    result = await collect_group_message(
        db_session,
        config=app_config,
        raw_update=raw_update,
        message=message,
    )

    [group] = (await db_session.scalars(select(GroupChat))).all()
    assert result.status == "ignored_unsupported"
    assert raw_update.processing_status == "ignored_unsupported"
    assert raw_update.error_type == "unsupported_message_type"
    assert (await db_session.scalars(select(GroupSummarySettings))).all() == []
