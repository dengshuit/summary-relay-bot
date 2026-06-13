from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from summary_relay_bot.telegram import userbot as userbot_boundary


class FakeChat:
    id = -1001


class FakeSender:
    id = 42
    username = "alice"
    first_name = "Alice"
    last_name = "Sender"


class FakeMessage:
    id = 10
    chat_id = -1001
    date = datetime(2026, 6, 13, tzinfo=timezone.utc)
    edit_date = None
    message = "hello"
    photo = None
    video = None
    voice = None
    audio = None
    sticker = None
    document = None
    media = None
    reply_to = None


class FakeNewMessageEvent:
    chat_id = -1001
    message = FakeMessage()

    async def get_chat(self):
        return FakeChat()

    async def get_sender(self):
        return FakeSender()


async def test_telethon_new_message_event_normalization_uses_summary_dto() -> None:
    message = await userbot_boundary._incoming_message_from_event(7, FakeNewMessageEvent())

    assert message.userbot_id == 7
    assert message.telegram_entity_id == -1001
    assert message.telegram_message_id == 10
    assert message.message_date == datetime(2026, 6, 13, tzinfo=timezone.utc)
    assert message.text == "hello"
    assert message.caption is None
    assert message.message_type == "text"
    assert message.sender_user_id == 42
    assert message.sender_username == "alice"
    assert message.sender_display_name == "Alice Sender"
    assert message.media_metadata is None


async def test_telethon_media_edit_event_normalization_uses_caption_and_metadata() -> None:
    event = SimpleNamespace(
        chat_id=-1001,
        message=SimpleNamespace(
            id=11,
            chat_id=-1001,
            date=datetime(2026, 6, 13, tzinfo=timezone.utc),
            edit_date=datetime(2026, 6, 13, 1, tzinfo=timezone.utc),
            message="updated caption",
            photo=object(),
            video=None,
            voice=None,
            audio=None,
            sticker=None,
            document=None,
            media=object(),
            file=SimpleNamespace(name="image.jpg", mime_type="image/jpeg", size=1234),
            reply_to=None,
        ),
        get_chat=lambda: _async_result(FakeChat()),
    )

    edit = await userbot_boundary._edited_message_from_event(7, event)

    assert edit.userbot_id == 7
    assert edit.telegram_entity_id == -1001
    assert edit.telegram_message_id == 11
    assert edit.edited_at == datetime(2026, 6, 13, 1, tzinfo=timezone.utc)
    assert edit.text is None
    assert edit.caption == "updated caption"
    assert edit.message_type == "photo"
    assert edit.media_metadata == {
        "media_type": "photo",
        "file_name": "image.jpg",
        "mime_type": "image/jpeg",
        "file_size": 1234,
    }


def test_telethon_delete_event_normalization_uses_deleted_ids() -> None:
    deleted = userbot_boundary._deleted_message_from_event(
        7,
        SimpleNamespace(
            chat_id=-1001,
            deleted_ids=[10, 11],
            date=datetime(2026, 6, 13, 2, tzinfo=timezone.utc),
        ),
    )

    assert deleted.userbot_id == 7
    assert deleted.telegram_entity_id == -1001
    assert deleted.telegram_message_ids == [10, 11]
    assert deleted.deleted_at == datetime(2026, 6, 13, 2, tzinfo=timezone.utc)


async def _async_result(value):
    return value
