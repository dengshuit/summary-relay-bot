from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select

from summary_relay_bot.db.models import SummaryEntity, SummaryMessage, SummaryState
from summary_relay_bot.db.repositories import ensure_summary_state
from summary_relay_bot.services.runtime_config import set_group_summary_settings
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.userbot_auth import create_summary_userbot
from summary_relay_bot.services.userbot_ingestion import (
    DeletedMessage,
    DiscoveredDialog,
    EditedMessage,
    IncomingMessage,
    ingest_userbot_message,
    ingest_userbot_message_edit,
    mark_userbot_message_deleted,
    refresh_userbot_dialogs,
)


def secret_service() -> SecretService:
    return SecretService(SecretService.generate_key())


async def _userbot(db_session):
    return await create_summary_userbot(
        db_session,
        secret_service=secret_service(),
        name="Main userbot",
        api_id=12345,
        api_hash="api-hash-secret",
        phone_number="+15550001111",
        session_string="string-session-secret",
        enabled=True,
    )


async def test_refresh_userbot_dialogs_creates_disabled_groups_and_ignores_channels(db_session) -> None:
    userbot = await _userbot(db_session)

    result = await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[
            DiscoveredDialog(
                telegram_entity_id=-1001,
                entity_type="megagroup",
                title="Megagroup",
                username="mega",
                telegram_access_hash=111,
            ),
            DiscoveredDialog(
                telegram_entity_id=-1002,
                entity_type="broadcast_channel",
                title="News",
            ),
        ],
    )

    groups = (await db_session.scalars(select(SummaryEntity))).all()
    states = (await db_session.scalars(select(SummaryState))).all()
    assert result.created == 1
    assert result.ignored == 1
    assert len(groups) == 1
    assert groups[0].chat_id == -1001
    assert groups[0].enabled is False
    assert groups[0].collection_status == "disabled"
    assert groups[0].chat_type == "megagroup"
    assert len(states) == 1


async def test_refresh_userbot_dialogs_updates_existing_metadata(db_session) -> None:
    userbot = await _userbot(db_session)
    await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[DiscoveredDialog(telegram_entity_id=-1001, entity_type="group", title="Old")],
    )

    result = await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[
            DiscoveredDialog(
                telegram_entity_id=-1001,
                entity_type="supergroup",
                title="New",
                username="new_group",
                telegram_access_hash=222,
            )
        ],
    )

    [group] = (await db_session.scalars(select(SummaryEntity))).all()
    assert result.updated == 1
    assert group.title == "New"
    assert group.username == "new_group"
    assert group.chat_type == "supergroup"
    assert group.telegram_access_hash == 222


async def test_ingest_message_ignores_disabled_group_and_stores_enabled_group(db_session) -> None:
    userbot = await _userbot(db_session)
    await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[DiscoveredDialog(telegram_entity_id=-1001, entity_type="group", title="Group")],
    )
    message = IncomingMessage(
        userbot_id=userbot.id,
        telegram_entity_id=-1001,
        telegram_message_id=10,
        message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
        text="hello",
        sender_user_id=42,
        sender_username="alice",
        sender_display_name="Alice",
    )

    ignored = await ingest_userbot_message(db_session, message)
    group = await db_session.scalar(select(SummaryEntity).where(SummaryEntity.chat_id == -1001))
    assert group is not None
    await set_group_summary_settings(
        db_session,
        group=group,
        enabled=True,
        interval_minutes=30,
    )
    stored = await ingest_userbot_message(db_session, message)
    deduped = await ingest_userbot_message(db_session, message)

    [row] = (await db_session.scalars(select(SummaryMessage))).all()
    assert ignored.status == "ignored_disabled_or_unknown"
    assert stored.status == "stored"
    assert stored.created is True
    assert deduped.status == "deduped"
    assert row.text == "hello"
    assert row.summary_content == "hello"
    assert row.message_type == "text"
    assert row.sender_username == "alice"


async def test_ingest_message_normalizes_media_placeholder(db_session) -> None:
    userbot = await _userbot(db_session)
    await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[DiscoveredDialog(telegram_entity_id=-1001, entity_type="group", title="Group")],
    )
    group = await db_session.scalar(select(SummaryEntity).where(SummaryEntity.chat_id == -1001))
    assert group is not None
    await set_group_summary_settings(db_session, group=group, enabled=True, interval_minutes=30)

    await ingest_userbot_message(
        db_session,
        IncomingMessage(
            userbot_id=userbot.id,
            telegram_entity_id=-1001,
            telegram_message_id=11,
            message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
            message_type="photo",
            media_metadata={"file_name": "image.jpg"},
        ),
    )

    [row] = (await db_session.scalars(select(SummaryMessage))).all()
    assert row.message_type == "photo"
    assert row.summary_content == "[media: photo]"
    assert row.media_metadata == {"file_name": "image.jpg"}


async def test_edit_updates_unsummarized_and_marks_after_summary_without_rewriting(db_session) -> None:
    userbot = await _userbot(db_session)
    await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[DiscoveredDialog(telegram_entity_id=-1001, entity_type="group", title="Group")],
    )
    group = await db_session.scalar(select(SummaryEntity).where(SummaryEntity.chat_id == -1001))
    assert group is not None
    await set_group_summary_settings(db_session, group=group, enabled=True, interval_minutes=30)
    await ingest_userbot_message(
        db_session,
        IncomingMessage(
            userbot_id=userbot.id,
            telegram_entity_id=-1001,
            telegram_message_id=12,
            message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
            text="before",
        ),
    )
    message = await db_session.scalar(select(SummaryMessage).where(SummaryMessage.telegram_message_id == 12))
    assert message is not None

    updated = await ingest_userbot_message_edit(
        db_session,
        EditedMessage(
            userbot_id=userbot.id,
            telegram_entity_id=-1001,
            telegram_message_id=12,
            edited_at=datetime(2026, 6, 13, 1, tzinfo=timezone.utc),
            text="after",
        ),
    )
    state = await ensure_summary_state(db_session, group)
    state.last_summary_sequence = message.id
    preserved = await ingest_userbot_message_edit(
        db_session,
        EditedMessage(
            userbot_id=userbot.id,
            telegram_entity_id=-1001,
            telegram_message_id=12,
            edited_at=datetime(2026, 6, 13, 2, tzinfo=timezone.utc),
            text="rewritten",
        ),
    )

    await db_session.refresh(message)
    assert updated.status == "updated"
    assert preserved.status == "marked_after_summary"
    assert message.text == "after"
    assert message.summary_content == "after"
    assert message.edited_after_summary_at is not None


async def test_delete_marks_known_messages(db_session) -> None:
    userbot = await _userbot(db_session)
    await refresh_userbot_dialogs(
        db_session,
        userbot=userbot,
        dialogs=[DiscoveredDialog(telegram_entity_id=-1001, entity_type="group", title="Group")],
    )
    group = await db_session.scalar(select(SummaryEntity).where(SummaryEntity.chat_id == -1001))
    assert group is not None
    await set_group_summary_settings(db_session, group=group, enabled=True, interval_minutes=30)
    await ingest_userbot_message(
        db_session,
        IncomingMessage(
            userbot_id=userbot.id,
            telegram_entity_id=-1001,
            telegram_message_id=13,
            message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
            text="delete me",
        ),
    )

    result = await mark_userbot_message_deleted(
        db_session,
        DeletedMessage(
            userbot_id=userbot.id,
            telegram_entity_id=-1001,
            telegram_message_ids=[13, 99],
            deleted_at=datetime(2026, 6, 13, 3, tzinfo=timezone.utc),
        ),
    )

    message = await db_session.scalar(select(SummaryMessage).where(SummaryMessage.telegram_message_id == 13))
    assert message is not None
    assert result.marked == 1
    assert result.missing == 1
    assert message.deleted_at is not None
