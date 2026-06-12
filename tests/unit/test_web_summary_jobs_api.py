from __future__ import annotations

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog, GroupChat, SummaryJob
from summary_relay_bot.db.repositories import (
    create_running_summary_job,
    ensure_summary_state,
    get_or_create_raw_update,
    store_group_message,
    upsert_group,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import create_llm_provider, create_summary_profile
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.app import create_web_app
from summary_relay_bot.web.routes import groups as groups_route


ADMIN_TOKEN = "webui-admin-secret"


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
    json: dict[str, object] | None = None,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers, json=json)


async def _seed_group(session, secret_service: SecretService) -> GroupChat:
    provider = await create_llm_provider(
        session,
        secret_service=secret_service,
        name="Primary Claude",
        provider_type="anthropic",
        api_key="llm-job-secret",
        default_model="claude-default",
    )
    await create_summary_profile(
        session,
        name="Default profile",
        llm_provider=provider,
        model=None,
        prompt_version="v7",
        is_default=True,
    )
    raw, _ = await get_or_create_raw_update(session, update_id=7001, payload={"update_id": 7001})
    group = await upsert_group(session, chat_id=-300, chat_type="supergroup", title="Job Group")
    await store_group_message(
        session,
        group=group,
        raw_update=raw,
        telegram_message_id=1,
        sender_user_id=42,
        sender_display_name="Sender",
        message_type="text",
        text="raw text should not leave job api",
        caption=None,
        summary_content="safe summary content",
    )
    return group


async def test_manual_summary_job_returns_202_and_can_be_polled_to_terminal_state(
    session_factory,
    monkeypatch,
) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        group = await _seed_group(session, secret_service)
        group_id = group.id

    def fake_schedule_manual_summary_job(*, session_factory, secret_service, group_id, job_id) -> None:
        async def mark_succeeded() -> None:
            async with session_scope(session_factory) as session:
                job = await session.get(SummaryJob, job_id)
                group = await session.get(GroupChat, group_id)
                assert job is not None
                assert group is not None
                job.status = "succeeded"
                job.started_at = job.created_at
                job.finished_at = job.created_at
                job.prompt_version = "v7"
                job.summary_profile_id = 1
                job.llm_provider_id = 1
                job.model = "claude-default"

        import asyncio

        asyncio.create_task(mark_succeeded())

    monkeypatch.setattr(groups_route, "schedule_manual_summary_job", fake_schedule_manual_summary_job)
    app = _web_app(session_factory, bootstrap_config)

    trigger = await _request(app, "POST", f"/api/groups/{group_id}/summary-jobs")
    assert trigger.status_code == 202
    payload = trigger.json()
    assert payload["job"]["status"] == "pending"
    assert payload["poll_url"] == f"/api/groups/{group_id}/summary-jobs/{payload['job']['id']}"

    poll = await _request(app, "GET", payload["poll_url"])
    assert poll.status_code == 200
    assert poll.json()["status"] == "succeeded"
    assert poll.json()["provider"] == "Primary Claude"
    assert poll.json()["profile_name"] == "Default profile"
    assert poll.json()["model"] == "claude-default"
    rendered = trigger.text + poll.text
    assert "llm-job-secret" not in rendered
    assert "raw text should not leave job api" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered
    async with session_factory() as session:
        audit_logs = (await session.scalars(select(AuditLog))).all()
    assert "trigger_summary" in [log.action for log in audit_logs]
    assert "llm-job-secret" not in str([log.redacted_after for log in audit_logs])


async def test_manual_summary_job_conflict_returns_409(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        group = await _seed_group(session, secret_service)
        state = await ensure_summary_state(session, group)
        active = await create_running_summary_job(
            session,
            group=group,
            trigger_type="manual",
            starting_sequence=state.last_summary_sequence,
        )
        assert active is not None
        group_id = group.id
        active_id = active.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        f"/api/groups/{group_id}/summary-jobs",
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "summary_job_conflict",
            "message": "该群有摘要正在生成",
            "details": {"active_job_id": active_id},
        }
    }


async def test_summary_job_api_requires_admin_token(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    post_response = await _request(app, "POST", "/api/groups/1/summary-jobs", token=None)
    poll_response = await _request(app, "GET", "/api/groups/1/summary-jobs/1", token=None)

    assert post_response.status_code == 401
    assert poll_response.status_code == 401
    assert post_response.json() == poll_response.json()
