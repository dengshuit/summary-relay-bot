from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from summary_relay_bot.db.models import SummaryJob, SummaryResult
from summary_relay_bot.db.repositories import get_or_create_raw_update, store_group_message, upsert_group
from summary_relay_bot.services import summary_jobs as summary_jobs_module
from summary_relay_bot.services.runtime_config import create_llm_provider, create_summary_profile
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.llm.client import SummaryLLMError
from summary_relay_bot.services.summary_jobs import SummaryReloadGate, run_summary_for_group


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


class FailingSummaryClient:
    def __init__(self, config) -> None:
        self.config = config

    async def summarize_group_messages(self, *, group_title, group_messages) -> str:
        raise SummaryLLMError("llm_failed_for_test")


async def create_runtime_summary_config(db_session):
    secret_service = SecretService(SecretService.generate_key())
    provider = await create_llm_provider(
        db_session,
        secret_service=secret_service,
        name="Runtime Provider",
        provider_type="anthropic",
        api_key="runtime-secret",
        default_model="runtime-model",
        timeout_seconds=7,
        max_retries=0,
        enabled=True,
    )
    profile = await create_summary_profile(
        db_session,
        name="Runtime Profile",
        llm_provider=provider,
        model="profile-model",
        prompt_version="runtime-v1",
        enabled=True,
        is_default=True,
    )
    return secret_service, provider, profile


async def test_manual_no_new_messages_returns_single_report_without_extra_send(app_config, db_session) -> None:
    secret_service, provider, profile = await create_runtime_summary_config(db_session)
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")
    bot = FakeBot()

    result = await run_summary_for_group(
        session=db_session,
        bot=bot,
        owner_id=1001,
        secret_service=secret_service,
        group=group,
        trigger_type="manual",
        notify_no_messages=True,
    )

    assert result.status == "succeeded"
    assert result.message == "No new messages to summarize for Group."
    assert bot.sent_messages == []
    [job] = (await db_session.scalars(select(SummaryJob))).all()
    assert job.prompt_version == "runtime-v1"
    assert job.llm_provider_id == provider.id
    assert job.summary_profile_id == profile.id
    assert job.model == "profile-model"


async def test_summary_persists_result_and_advances_cursor_without_telegram_delivery(
    app_config,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(summary_jobs_module, "PrivacyAwareSummaryClient", FakeSummaryClient)
    secret_service, provider, profile = await create_runtime_summary_config(db_session)
    raw, _ = await get_or_create_raw_update(db_session, update_id=501, payload={"update_id": 501})
    group = await upsert_group(db_session, chat_id=-200, chat_type="supergroup", title="Group")
    scheduled_notifications: list[int] = []
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
        owner_id=1001,
        secret_service=secret_service,
        group=group,
        trigger_type="manual",
        notify_no_messages=True,
        schedule_notification=scheduled_notifications.append,
    )

    [job] = (await db_session.scalars(select(SummaryJob))).all()
    [summary_result] = (await db_session.scalars(select(SummaryResult))).all()
    assert result.status == "succeeded"
    assert result.cursor_advanced is True
    assert result.message == "summary persisted and cursor advanced"
    assert job.status == "succeeded"
    assert job.prompt_version == "runtime-v1"
    assert job.llm_provider_id == provider.id
    assert job.summary_profile_id == profile.id
    assert job.model == "profile-model"
    assert summary_result.summary_text == "summary text"
    assert summary_result.interval_start_sequence == 0
    assert summary_result.interval_end_sequence == 1
    assert summary_result.llm_provider_id == provider.id
    assert summary_result.summary_profile_id == profile.id
    assert summary_result.model == "profile-model"
    assert scheduled_notifications == [summary_result.id]
    assert group.summary_state is not None
    assert group.summary_state.last_summary_sequence == 1


async def test_llm_failure_marks_summary_job_failed_without_cursor_advance(
    app_config,
    db_session,
    monkeypatch,
) -> None:
    monkeypatch.setattr(summary_jobs_module, "PrivacyAwareSummaryClient", FailingSummaryClient)
    secret_service, _provider, _profile = await create_runtime_summary_config(db_session)
    raw, _ = await get_or_create_raw_update(db_session, update_id=502, payload={"update_id": 502})
    group = await upsert_group(db_session, chat_id=-250, chat_type="supergroup", title="Group")
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
        bot=FakeBot(),
        owner_id=1001,
        secret_service=secret_service,
        group=group,
        trigger_type="manual",
        notify_no_messages=True,
    )

    [job] = (await db_session.scalars(select(SummaryJob))).all()
    assert result.status == "failed"
    assert result.cursor_advanced is False
    assert job.status == "failed"
    assert job.error_type == "llm_failed"
    assert job.cutoff_sequence == 1
    assert group.summary_state is not None
    assert group.summary_state.last_summary_sequence == 0
    assert (await db_session.scalars(select(SummaryResult))).all() == []


async def test_runtime_config_failure_marks_summary_job_failed(app_config, db_session) -> None:
    group = await upsert_group(db_session, chat_id=-300, chat_type="group", title="Group")

    result = await run_summary_for_group(
        session=db_session,
        bot=FakeBot(),
        owner_id=1001,
        secret_service=SecretService(SecretService.generate_key()),
        group=group,
        trigger_type="manual",
        notify_no_messages=True,
    )

    [job] = (await db_session.scalars(select(SummaryJob))).all()
    assert result.status == "failed"
    assert job.status == "failed"
    assert job.error_type == "runtime_config_error"
    assert job.prompt_version is None
    assert job.llm_provider_id is None
    assert job.summary_profile_id is None
    assert job.model is None


async def test_summary_reload_gate_tracks_active_summary_and_releases_after_exception() -> None:
    gate = SummaryReloadGate()

    assert await gate.has_active_bot_delivery_summary() is False
    try:
        async with gate.enter_bot_delivery_summary():
            assert await gate.has_active_bot_delivery_summary() is True
            raise RuntimeError("summary failed")
    except RuntimeError:
        pass

    assert await gate.has_active_bot_delivery_summary() is False


async def test_summary_for_group_does_not_enter_bot_delivery_reload_gate(db_session) -> None:
    gate = SummaryReloadGate()
    group = await upsert_group(db_session, chat_id=-400, chat_type="group", title="Group")
    assert await gate.try_begin_runtime_reload() is True
    try:
        result = await run_summary_for_group(
            session=db_session,
            bot=FakeBot(),
            owner_id=1001,
            secret_service=SecretService(SecretService.generate_key()),
            group=group,
            trigger_type="manual",
            notify_no_messages=True,
            reload_gate=gate,
        )
    finally:
        await gate.finish_runtime_reload()

    assert result.status == "failed"
    assert result.message == "runtime summary config failed; cursor unchanged"
    [job] = (await db_session.scalars(select(SummaryJob))).all()
    assert job.status == "failed"
