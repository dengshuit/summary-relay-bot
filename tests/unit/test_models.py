from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from summary_relay_bot.db.models import AdminReplyMap, GroupMessage, SummaryJob, TelegramUpdate
from summary_relay_bot.db.repositories import (
    create_reply_map,
    get_or_create_raw_update,
    store_group_message,
    upsert_group,
    upsert_private_user,
)


async def test_raw_update_id_is_idempotent(db_session) -> None:
    first, created_first = await get_or_create_raw_update(
        db_session,
        update_id=10,
        payload={"update_id": 10, "message": {"text": "hello"}},
    )
    second, created_second = await get_or_create_raw_update(
        db_session,
        update_id=10,
        payload={"update_id": 10, "message": {"text": "hello again"}},
    )

    rows = (await db_session.scalars(select(TelegramUpdate))).all()
    assert created_first is True
    assert created_second is False
    assert second.id == first.id
    assert len(rows) == 1


async def test_reply_map_prevents_ambiguous_admin_message_mapping(db_session) -> None:
    private_user = await upsert_private_user(
        db_session,
        telegram_user_id=2002,
        username="alice",
        first_name="Alice",
        last_name=None,
    )

    first, created_first = await create_reply_map(
        db_session,
        private_user=private_user,
        admin_chat_id=1001,
        admin_message_id=50,
        source_kind="info_card",
    )
    second, created_second = await create_reply_map(
        db_session,
        private_user=private_user,
        admin_chat_id=1001,
        admin_message_id=50,
        source_kind="copied_message",
    )

    rows = (await db_session.scalars(select(AdminReplyMap))).all()
    assert created_first is True
    assert created_second is False
    assert second.id == first.id
    assert len(rows) == 1


async def test_group_media_metadata_has_no_file_body_column(db_session) -> None:
    raw, _ = await get_or_create_raw_update(db_session, update_id=11, payload={"update_id": 11})
    group = await upsert_group(
        db_session,
        chat_id=-100,
        chat_type="supergroup",
        title="Test group",
    )

    stored, created = await store_group_message(
        db_session,
        group=group,
        raw_update=raw,
        telegram_message_id=9,
        sender_user_id=123,
        sender_display_name="Alice",
        message_type="document",
        text=None,
        caption="read this",
        summary_content="[document: file.pdf] read this",
        file_id="file-id",
        file_unique_id="unique-id",
        file_name="file.pdf",
        mime_type="application/pdf",
        file_size=1234,
        media_metadata={"file_id": "file-id", "message_type": "document"},
    )

    assert created is True
    assert stored.file_id == "file-id"
    assert stored.file_name == "file.pdf"
    assert not hasattr(stored, "file_body")
    assert "file_body" not in GroupMessage.__table__.columns


async def test_summary_jobs_allow_only_one_active_job_per_group(db_session) -> None:
    group = await upsert_group(db_session, chat_id=-300, chat_type="supergroup", title="Group")
    db_session.add(
        SummaryJob(
            group=group,
            chat_id=group.chat_id,
            trigger_type="manual",
            status="pending",
            starting_sequence=0,
        )
    )
    await db_session.flush()
    db_session.add(
        SummaryJob(
            group=group,
            chat_id=group.chat_id,
            trigger_type="manual",
            status="running",
            starting_sequence=0,
        )
    )

    with pytest.raises(IntegrityError):
        await db_session.flush()
