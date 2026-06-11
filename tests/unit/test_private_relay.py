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
        self.sent_messages: list[tuple[int, str]] = []
        self.copy_calls: list[tuple[int, int, int]] = []

    async def send_message(self, chat_id: int, text: str):
        self.sent_messages.append((chat_id, text))
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
        message=private_message(),
    )

    attempts = (await db_session.scalars(select(DeliveryAttempt).order_by(DeliveryAttempt.purpose))).all()
    reply_maps = (await db_session.scalars(select(AdminReplyMap))).all()
    [inbound] = (await db_session.scalars(select(PrivateMessage))).all()

    assert sorted(attempt.status for attempt in attempts) == ["failed", "mapped"]
    assert len(reply_maps) == 1
    assert reply_maps[0].source_kind == "info_card"
    assert inbound.delivery_status == "partial_failed"
    assert raw_update.processing_status == "private_relay_partial"
    assert any("Could not create a safe reply mapping" in text for _, text in bot.sent_messages)
