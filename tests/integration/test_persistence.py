from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select

from summary_relay_bot.db.models import PrivateMessage, SummaryJob, TelegramUpdate, utcnow
from summary_relay_bot.db.repositories import (
    create_private_message,
    create_running_summary_job,
    ensure_summary_state,
    get_or_create_raw_update,
    messages_after_sequence,
    redact_raw_payloads_older_than,
    store_group_message,
    upsert_group,
    upsert_private_user,
)


async def test_recovery_can_find_raw_persisted_update_without_duplicate_derived_rows(db_session) -> None:
    raw, _ = await get_or_create_raw_update(
        db_session,
        update_id=21,
        payload={"update_id": 21, "message": {"message_id": 1}},
    )
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")

    first, created_first = await store_group_message(
        db_session,
        group=group,
        raw_update=raw,
        telegram_message_id=1,
        sender_user_id=None,
        sender_display_name=None,
        message_type="text",
        text="hello",
        caption=None,
        summary_content="hello",
    )
    second, created_second = await store_group_message(
        db_session,
        group=group,
        raw_update=raw,
        telegram_message_id=1,
        sender_user_id=None,
        sender_display_name=None,
        message_type="text",
        text="hello",
        caption=None,
        summary_content="hello",
    )

    assert created_first is True
    assert created_second is False
    assert second.id == first.id


async def test_summary_sequence_includes_late_lower_telegram_message_id(db_session) -> None:
    raw1, _ = await get_or_create_raw_update(db_session, update_id=31, payload={"update_id": 31})
    raw2, _ = await get_or_create_raw_update(db_session, update_id=32, payload={"update_id": 32})
    group = await upsert_group(db_session, chat_id=-200, chat_type="supergroup", title="Group")
    state = await ensure_summary_state(db_session, group)

    first, _ = await store_group_message(
        db_session,
        group=group,
        raw_update=raw1,
        telegram_message_id=20,
        sender_user_id=None,
        sender_display_name=None,
        message_type="text",
        text="newer telegram id committed first",
        caption=None,
        summary_content="newer telegram id committed first",
    )
    state.last_summary_sequence = first.id
    late, _ = await store_group_message(
        db_session,
        group=group,
        raw_update=raw2,
        telegram_message_id=10,
        sender_user_id=None,
        sender_display_name=None,
        message_type="text",
        text="lower telegram id committed later",
        caption=None,
        summary_content="lower telegram id committed later",
    )

    messages = await messages_after_sequence(db_session, group=group, sequence=state.last_summary_sequence)

    assert [message.id for message in messages] == [late.id]
    assert messages[0].telegram_message_id == 10


async def test_only_one_running_summary_job_per_group(db_session) -> None:
    group = await upsert_group(db_session, chat_id=-300, chat_type="group", title="Group")

    first = await create_running_summary_job(
        db_session,
        group=group,
        trigger_type="manual",
        starting_sequence=0,
    )
    second = await create_running_summary_job(
        db_session,
        group=group,
        trigger_type="scheduled",
        starting_sequence=0,
    )

    assert first is not None
    assert second is None
    rows = (await db_session.scalars(select(SummaryJob).where(SummaryJob.status == "running"))).all()
    assert len(rows) == 1


async def test_retention_redacts_raw_payload_without_deleting_business_metadata(db_session) -> None:
    raw, _ = await get_or_create_raw_update(db_session, update_id=41, payload={"update_id": 41, "message": "secret"})
    raw.received_at = utcnow() - timedelta(days=60)
    private_user = await upsert_private_user(
        db_session,
        telegram_user_id=2002,
        username=None,
        first_name="Alice",
        last_name=None,
    )
    await create_private_message(
        db_session,
        private_user=private_user,
        raw_update=raw,
        direction="incoming",
        telegram_chat_id=2002,
        telegram_message_id=5,
        message_type="text",
        text="private content",
    )

    redacted = await redact_raw_payloads_older_than(
        db_session,
        older_than=utcnow() - timedelta(days=30),
    )

    private_messages = (await db_session.scalars(select(PrivateMessage))).all()
    assert redacted == 1
    assert raw.payload is None
    assert raw.payload_retained is False
    assert len(private_messages) == 1
    assert private_messages[0].text == "private content"
