from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from summary_relay_bot.db.models import PrivateMessage
from summary_relay_bot.db.repositories import create_reply_map, upsert_private_user
from summary_relay_bot.services import admin_replies as admin_replies_module
from summary_relay_bot.services.admin_replies import AdminReplyError, route_admin_reply, send_reply_command


class FailingBot:
    async def send_message(self, chat_id: int, text: str):
        raise RuntimeError("forbidden")


class RecordingBot:
    def __init__(self) -> None:
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str):
        self.sent_messages.append((chat_id, text))
        return SimpleNamespace(message_id=len(self.sent_messages) + 100)


async def test_reply_command_reports_terminal_delivery_context(app_config, db_session, monkeypatch) -> None:
    private_user = await upsert_private_user(
        db_session,
        telegram_user_id=2002,
        username="alice",
        first_name="Alice",
        last_name=None,
    )

    monkeypatch.setattr(
        admin_replies_module,
        "classify_telegram_error",
        lambda exc: SimpleNamespace(
            error_type="telegram_forbidden",
            message="TelegramForbiddenError: bot was blocked by the user",
            retryable=False,
        ),
    )

    with pytest.raises(AdminReplyError, match="blocked the bot|cannot receive"):
        await send_reply_command(
            session=db_session,
            bot=FailingBot(),
            user_id=private_user.telegram_user_id,
            text="hello",
        )

    [outgoing] = (await db_session.scalars(select(PrivateMessage))).all()
    assert outgoing.direction == "outgoing"
    assert outgoing.delivery_status == "blocked"
    assert outgoing.error_type == "telegram_forbidden"


async def test_reply_command_delivers_to_known_private_user(db_session) -> None:
    private_user = await upsert_private_user(
        db_session,
        telegram_user_id=2002,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    bot = RecordingBot()

    result = await send_reply_command(
        session=db_session,
        bot=bot,
        user_id=private_user.telegram_user_id,
        text=" hello ",
    )

    [outgoing] = (await db_session.scalars(select(PrivateMessage))).all()
    assert result == "Reply delivered."
    assert bot.sent_messages == [(2002, "hello")]
    assert outgoing.direction == "outgoing"
    assert outgoing.delivery_status == "sent"
    assert outgoing.telegram_message_id == 101


async def test_reply_command_rejects_unknown_private_user(db_session) -> None:
    with pytest.raises(AdminReplyError, match="unknown"):
        await send_reply_command(
            session=db_session,
            bot=RecordingBot(),
            user_id=9999,
            text="hello",
        )


async def test_mapped_owner_reply_delivers_to_private_user(db_session) -> None:
    private_user = await upsert_private_user(
        db_session,
        telegram_user_id=2002,
        username="alice",
        first_name="Alice",
        last_name=None,
    )
    await create_reply_map(
        db_session,
        private_user=private_user,
        admin_chat_id=1001,
        admin_message_id=50,
        source_kind="text_message",
    )
    bot = RecordingBot()
    message = SimpleNamespace(
        message_id=60,
        text="reply through map",
        caption=None,
        reply_to_message=SimpleNamespace(message_id=50),
    )

    result = await route_admin_reply(
        session=db_session,
        bot=bot,
        owner_id=1001,
        message=message,
    )

    [outgoing] = (await db_session.scalars(select(PrivateMessage))).all()
    assert result == "Reply delivered."
    assert bot.sent_messages == [(2002, "reply through map")]
    assert outgoing.direction == "outgoing"
    assert outgoing.delivery_status == "sent"
    assert outgoing.text == "reply through map"
