from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from summary_relay_bot.db.models import SummaryJob
from summary_relay_bot.db.repositories import get_or_create_raw_update, store_group_message, upsert_group
from summary_relay_bot.handlers.admin import handle_manual_summary
from summary_relay_bot.services import summary_jobs as summary_jobs_module
from summary_relay_bot.services.summary_jobs import run_summary_for_group


class FakeBot:
    def __init__(self, *, fail_send: bool = False) -> None:
        self.fail_send = fail_send
        self.sent_messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str):
        self.sent_messages.append((chat_id, text))
        if self.fail_send:
            raise RuntimeError("telegram delivery failed")
        return SimpleNamespace(message_id=len(self.sent_messages))


class FakeSummaryClient:
    def __init__(self, config) -> None:
        self.config = config

    async def summarize_group_messages(self, *, group_title, group_messages) -> str:
        return "summary text"


class FakeAdminMessage:
    def __init__(self, text: str) -> None:
        self.text = text
        self.bot = FakeBot()
        self.answers: list[str] = []

    async def answer(self, text: str) -> None:
        self.answers.append(text)


async def test_manual_summary_rejects_non_integer_chat_id(app_config, session_factory) -> None:
    message = FakeAdminMessage("/summary not-a-number")

    await handle_manual_summary(message, app_config, session_factory)

    assert message.answers == ["Usage: /summary [chat_id]"]


async def test_manual_no_new_messages_returns_single_report_without_extra_send(app_config, db_session) -> None:
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")
    bot = FakeBot()

    result = await run_summary_for_group(
        session=db_session,
        bot=bot,
        config=app_config,
        group=group,
        trigger_type="manual",
        notify_no_messages=True,
    )

    assert result.status == "succeeded"
    assert result.message == "No new messages to summarize for Group."
    assert bot.sent_messages == []


async def test_telegram_delivery_failure_blocks_job_without_cursor_advance(
    app_config,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(summary_jobs_module, "PrivacyAwareSummaryClient", FakeSummaryClient)
    raw, _ = await get_or_create_raw_update(db_session, update_id=501, payload={"update_id": 501})
    group = await upsert_group(db_session, chat_id=-200, chat_type="supergroup", title="Group")
    await store_group_message(
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

    result = await run_summary_for_group(
        session=db_session,
        bot=FakeBot(fail_send=True),
        config=app_config,
        group=group,
        trigger_type="manual",
        notify_no_messages=True,
    )

    [job] = (await db_session.scalars(select(SummaryJob))).all()
    assert result.status == "blocked"
    assert result.cursor_advanced is False
    assert job.status == "blocked"
    assert group.summary_state is not None
    assert group.summary_state.last_summary_sequence == 0
