from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from summary_relay_bot.db.models import AdminReplyMap, DeliveryAttempt, PrivateMessage
from summary_relay_bot.db.repositories import get_or_create_raw_update
from summary_relay_bot.services import private_relay as private_relay_module
from summary_relay_bot.services.private_relay import relay_private_message


class FakeBot:
    def __init__(self) -> None:
        self.next_message_id = 100
        self.sent_messages: list[tuple[int, str, dict[str, object]]] = []
        self.copy_calls: list[tuple[int, int, int]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        self.sent_messages.append((chat_id, text, kwargs))
        self.next_message_id += 1
        return SimpleNamespace(message_id=self.next_message_id)

    async def copy_message(self, *, chat_id: int, from_chat_id: int, message_id: int):
        self.copy_calls.append((chat_id, from_chat_id, message_id))
        self.next_message_id += 1
        return SimpleNamespace(message_id=self.next_message_id)


def private_message() -> SimpleNamespace:
    return SimpleNamespace(
        message_id=55,
        text="hello owner",
        caption=None,
        chat=SimpleNamespace(id=2002, type="private"),
        from_user=SimpleNamespace(
            id=2002,
            username="alice",
            first_name="Alice",
            last_name=None,
            language_code="en",
        ),
    )


def private_photo_message() -> SimpleNamespace:
    message = private_message()
    message.text = None
    message.photo = [SimpleNamespace(file_id="file-1", file_unique_id="unique-1")]
    return message


async def test_private_relay_sends_text_with_user_context_and_maps_reply(
    db_session,
) -> None:
    raw_update, _ = await get_or_create_raw_update(
        db_session,
        update_id=700,
        payload={"update_id": 700},
    )
    bot = FakeBot()

    await relay_private_message(
        session=db_session,
        bot=bot,
        owner_id=1001,
        raw_update=raw_update,
        message=private_message(),
    )

    attempts = (await db_session.scalars(select(DeliveryAttempt))).all()
    reply_maps = (await db_session.scalars(select(AdminReplyMap))).all()
    [inbound] = (await db_session.scalars(select(PrivateMessage))).all()

    assert len(bot.sent_messages) == 1
    chat_id, text, kwargs = bot.sent_messages[0]
    assert chat_id == 1001
    assert kwargs["parse_mode"] == "HTML"
    assert "<blockquote>From: Alice (@alice)" in text
    assert "User ID: 2002" in text
    assert "hello owner" in text
    assert bot.copy_calls == []
    assert attempts[0].purpose == "private_text_message"
    assert attempts[0].status == "mapped"
    assert len(reply_maps) == 1
    assert reply_maps[0].source_kind == "text_message"
    assert inbound.delivery_status == "sent"
    assert raw_update.processing_status == "private_relayed"


async def test_private_relay_copies_media_then_replies_with_context_card(
    db_session,
) -> None:
    raw_update, _ = await get_or_create_raw_update(
        db_session,
        update_id=701,
        payload={"update_id": 701},
    )
    bot = FakeBot()

    await relay_private_message(
        session=db_session,
        bot=bot,
        owner_id=1001,
        raw_update=raw_update,
        message=private_photo_message(),
    )

    attempts = (await db_session.scalars(select(DeliveryAttempt).order_by(DeliveryAttempt.purpose))).all()
    reply_maps = (await db_session.scalars(select(AdminReplyMap).order_by(AdminReplyMap.source_kind))).all()
    [inbound] = (await db_session.scalars(select(PrivateMessage))).all()

    assert bot.copy_calls == [(1001, 2002, 55)]
    assert len(bot.sent_messages) == 1
    _chat_id, text, kwargs = bot.sent_messages[0]
    assert text.startswith("Message context")
    assert kwargs["reply_to_message_id"] == 101
    assert sorted(attempt.purpose for attempt in attempts) == [
        "private_context_card",
        "private_copy_message",
    ]
    assert sorted(attempt.status for attempt in attempts) == ["mapped", "mapped"]
    assert [reply_map.source_kind for reply_map in reply_maps] == ["context_card", "copied_message"]
    assert inbound.delivery_status == "sent"
    assert raw_update.processing_status == "private_relayed"


async def test_private_relay_marks_copy_mapping_failure_as_partial_and_warns(
    db_session,
    monkeypatch,
) -> None:
    raw_update, _ = await get_or_create_raw_update(
        db_session,
        update_id=701,
        payload={"update_id": 701},
    )
    bot = FakeBot()
    real_create_reply_map = private_relay_module.create_reply_map

    async def create_reply_map_with_copy_failure(session, **kwargs):
        if kwargs["source_kind"] == "copied_message":
            raise RuntimeError("database unavailable")
        return await real_create_reply_map(session, **kwargs)

    monkeypatch.setattr(private_relay_module, "create_reply_map", create_reply_map_with_copy_failure)

    await relay_private_message(
        session=db_session,
        bot=bot,
        owner_id=1001,
        raw_update=raw_update,
        message=private_photo_message(),
    )

    attempts = (await db_session.scalars(select(DeliveryAttempt).order_by(DeliveryAttempt.purpose))).all()
    reply_maps = (await db_session.scalars(select(AdminReplyMap))).all()
    [inbound] = (await db_session.scalars(select(PrivateMessage))).all()

    assert sorted(attempt.status for attempt in attempts) == ["failed", "mapped"]
    assert len(reply_maps) == 1
    assert reply_maps[0].source_kind == "context_card"
    assert inbound.delivery_status == "partial_failed"
    assert raw_update.processing_status == "private_relay_partial"
    assert any("Could not create a safe reply mapping" in text for _, text, _kwargs in bot.sent_messages)
