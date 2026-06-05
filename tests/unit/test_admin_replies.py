from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from summary_relay_bot.db.models import PrivateMessage
from summary_relay_bot.db.repositories import upsert_private_user
from summary_relay_bot.services import admin_replies as admin_replies_module
from summary_relay_bot.services.admin_replies import AdminReplyError, send_reply_command


class FailingBot:
    async def send_message(self, chat_id: int, text: str):
        raise RuntimeError("forbidden")


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
