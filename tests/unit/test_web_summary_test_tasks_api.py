from __future__ import annotations

import asyncio
from datetime import timedelta

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import SummaryJob, SummaryResult, SummaryState
from summary_relay_bot.db.repositories import (
    ensure_summary_state,
    get_or_create_raw_update,
    store_group_message,
    upsert_group,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.llm.client import SummaryLLMError
from summary_relay_bot.services import summary_test_tasks as summary_test_tasks_module
from summary_relay_bot.services.runtime_config import create_llm_provider, create_summary_profile
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.summary_test_tasks import SummaryTestTaskRegistry
from summary_relay_bot.web.app import create_web_app


ADMIN_TOKEN = "webui-admin-secret"
TERMINAL_STATUSES = {"succeeded", "failed", "canceled"}


def _bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token=ADMIN_TOKEN,
    )


def _web_app(session_factory, bootstrap_config: BootstrapConfig):
    return create_web_app(
        bootstrap_config=bootstrap_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
    )


async def _request(
    app,
    method: str,
    path: str,
    *,
    token: str | None = ADMIN_TOKEN,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers)


class FakeSummaryClient:
    seen_messages = []

    def __init__(self, config) -> None:
        self.config = config

    async def summarize_group_messages(self, *, group_title, group_messages) -> str:
        self.__class__.seen_messages = list(group_messages)
        return "generated test summary"


class FailingSummaryClient:
    def __init__(self, config) -> None:
        self.config = config

    async def summarize_group_messages(self, *, group_title, group_messages) -> str:
        raise SummaryLLMError("provider timeout")


class BlockingSummaryClient:
    def __init__(self, config) -> None:
        self.config = config

    async def summarize_group_messages(self, *, group_title, group_messages) -> str:
        await asyncio.Event().wait()
        return "never reached"


async def _seed_runtime_config(session, secret_service: SecretService) -> None:
    provider = await create_llm_provider(
        session,
        secret_service=secret_service,
        name="Primary Claude",
        provider_type="anthropic",
        api_key="llm-test-secret",
        default_model="claude-default",
    )
    await create_summary_profile(
        session,
        name="Default profile",
        llm_provider=provider,
        model=None,
        prompt_version="test-v1",
        is_default=True,
    )


async def _seed_group_messages(
    session,
    *,
    chat_id: int,
    title: str,
    count: int,
):
    raw, _ = await get_or_create_raw_update(session, update_id=9000 + abs(chat_id), payload={"safe": False})
    group = await upsert_group(session, chat_id=chat_id, chat_type="supergroup", title=title)
    for index in range(1, count + 1):
        await store_group_message(
            session,
            group=group,
            raw_update=raw,
            telegram_message_id=index,
            sender_user_id=42,
            sender_display_name="Sender",
            message_type="text",
            text=f"raw group text {index} must not leak",
            caption=None,
            summary_content=f"safe message {index}",
        )
    return group


async def _poll_until_terminal(app, poll_url: str) -> dict:
    for _ in range(50):
        response = await _request(app, "GET", poll_url)
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in TERMINAL_STATUSES:
            return payload
        await asyncio.sleep(0.01)
    raise AssertionError("summary test task did not reach a terminal state")


async def test_summary_test_task_uses_latest_50_without_cursor_or_history_changes(
    session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setattr(summary_test_tasks_module, "PrivacyAwareSummaryClient", FakeSummaryClient)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        await _seed_runtime_config(session, secret_service)
        group = await _seed_group_messages(session, chat_id=-901, title="Test Group", count=60)
        state = await ensure_summary_state(session, group)
        state.last_summary_sequence = 20
        group_id = group.id

    app = _web_app(session_factory, bootstrap_config)
    trigger = await _request(app, "POST", f"/api/groups/{group_id}/summary-test-tasks")
    assert trigger.status_code == 202
    assert trigger.json()["poll_url"] == f"/api/groups/{group_id}/summary-test-tasks/{trigger.json()['task']['id']}"

    task = await _poll_until_terminal(app, trigger.json()["poll_url"])

    assert task["status"] == "succeeded"
    assert task["message_count"] == 50
    assert task["sequence_range"] == "11-60"
    assert task["summary_text"] == "generated test summary"
    assert [message.summary_content for message in FakeSummaryClient.seen_messages] == [
        f"safe message {index}" for index in range(11, 61)
    ]
    rendered = trigger.text + str(task)
    assert "llm-test-secret" not in rendered
    assert "raw group text" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered

    async with session_factory() as session:
        state = await session.scalar(select(SummaryState).where(SummaryState.group_id == group_id))
        jobs = (await session.scalars(select(SummaryJob))).all()
        results = (await session.scalars(select(SummaryResult))).all()

    assert state is not None
    assert state.last_summary_sequence == 20
    assert state.last_summary_at is None
    assert jobs == []
    assert results == []


async def test_summary_test_task_failure_returns_safe_error(session_factory, monkeypatch) -> None:
    monkeypatch.setattr(summary_test_tasks_module, "PrivacyAwareSummaryClient", FailingSummaryClient)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        await _seed_runtime_config(session, secret_service)
        group = await _seed_group_messages(session, chat_id=-902, title="Failing Group", count=1)
        group_id = group.id

    app = _web_app(session_factory, bootstrap_config)
    trigger = await _request(app, "POST", f"/api/groups/{group_id}/summary-test-tasks")
    assert trigger.status_code == 202

    task = await _poll_until_terminal(app, trigger.json()["poll_url"])

    assert task["status"] == "failed"
    assert task["error_type"] == "llm_failed"
    assert task["error_message"] == "provider timeout"
    assert task["summary_text"] is None


async def test_summary_test_task_registry_rejects_when_active_task_limit_is_reached(
    session_factory,
    monkeypatch,
) -> None:
    monkeypatch.setattr(summary_test_tasks_module, "PrivacyAwareSummaryClient", BlockingSummaryClient)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        await _seed_runtime_config(session, secret_service)
        group = await _seed_group_messages(session, chat_id=-903, title="Busy Group", count=1)
        group_id = group.id

    app = _web_app(session_factory, bootstrap_config)
    created = []
    for _ in range(5):
        response = await _request(app, "POST", f"/api/groups/{group_id}/summary-test-tasks")
        assert response.status_code == 202
        created.append(response.json()["task"]["id"])

    busy = await _request(app, "POST", f"/api/groups/{group_id}/summary-test-tasks")

    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "summary_test_task_busy"
    for task_id in created:
        await _request(app, "POST", f"/api/groups/{group_id}/summary-test-tasks/{task_id}/cancel")


async def test_summary_test_task_registry_expires_terminal_tasks(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        await _seed_runtime_config(session, secret_service)
        group = await _seed_group_messages(session, chat_id=-904, title="TTL Group", count=0)
        group_id = group.id
        chat_id = group.chat_id

    registry = SummaryTestTaskRegistry(max_tasks=1, terminal_ttl=timedelta(seconds=0))
    first = await registry.create_task(
        session_factory=session_factory,
        secret_service=secret_service,
        group_id=group_id,
        chat_id=chat_id,
    )
    for _ in range(50):
        first_state = await registry.get_task(first.id)
        if first_state is None or first_state.status == "succeeded":
            break
        await asyncio.sleep(0.01)
    else:
        raise AssertionError("first task did not finish")

    second = await registry.create_task(
        session_factory=session_factory,
        secret_service=secret_service,
        group_id=group_id,
        chat_id=chat_id,
    )

    assert second.id != first.id


async def test_summary_test_task_api_requires_admin_token(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    post_response = await _request(app, "POST", "/api/groups/1/summary-test-tasks", token=None)
    poll_response = await _request(app, "GET", "/api/groups/1/summary-test-tasks/task-id", token=None)
    cancel_response = await _request(
        app,
        "POST",
        "/api/groups/1/summary-test-tasks/task-id/cancel",
        token=None,
    )

    assert post_response.status_code == 401
    assert poll_response.status_code == 401
    assert cancel_response.status_code == 401
    assert post_response.json() == poll_response.json() == cancel_response.json()
