from __future__ import annotations

import httpx

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.repositories import (
    create_running_summary_job,
    create_summary_result,
    ensure_summary_state,
    finish_summary_job,
    get_or_create_raw_update,
    store_group_message,
    upsert_group,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import create_llm_provider, create_summary_profile
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.app import create_web_app


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
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers)


async def _seed_summary(session, secret_service: SecretService):
    provider = await create_llm_provider(
        session,
        secret_service=secret_service,
        name="Primary Claude",
        provider_type="anthropic",
        api_key="llm-summary-secret",
        default_model="claude-default",
    )
    profile = await create_summary_profile(
        session,
        name="Default profile",
        llm_provider=provider,
        is_default=True,
    )
    raw, _ = await get_or_create_raw_update(
        session,
        update_id=8801,
        payload={"message": {"text": "raw update body must not leak"}},
    )
    group = await upsert_group(
        session,
        chat_id=-1008801,
        chat_type="supergroup",
        title="Summary Group",
        username="summary_group",
    )
    message, _ = await store_group_message(
        session,
        group=group,
        raw_update=raw,
        telegram_message_id=1,
        sender_user_id=42,
        sender_display_name="Alice",
        message_type="text",
        text="raw group text must not leak",
        caption=None,
        summary_content="safe source summary content",
    )
    state = await ensure_summary_state(session, group)
    job = await create_running_summary_job(
        session,
        group=group,
        trigger_type="manual",
        starting_sequence=state.last_summary_sequence,
    )
    assert job is not None
    job.llm_provider_id = provider.id
    job.summary_profile_id = profile.id
    job.model = "claude-default"
    await create_summary_result(
        session,
        job=job,
        group=group,
        summary_text="Generated summary content",
        delivered_admin_chat_id=123,
        delivered_message_id=456,
        prompt_version=profile.prompt_version,
        llm_provider_id=provider.id,
        summary_profile_id=profile.id,
        model="claude-default",
        interval_start_sequence=state.last_summary_sequence,
        interval_end_sequence=message.id,
    )
    await finish_summary_job(session, job, "succeeded", cutoff_sequence=message.id)
    return job, group


async def test_get_summaries_returns_generated_content_without_raw_messages(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        job, group = await _seed_summary(session, secret_service)

    response = await _request(_web_app(session_factory, bootstrap_config), "GET", "/api/summaries")

    assert response.status_code == 200
    payload = response.json()
    assert payload["items"][0]["job_id"] == job.id
    assert payload["items"][0]["group_id"] == group.id
    assert payload["items"][0]["group_title"] == "Summary Group"
    assert payload["items"][0]["provider"] == "Primary Claude"
    assert payload["items"][0]["profile_name"] == "Default profile"
    assert payload["items"][0]["content"] == "Generated summary content"
    rendered = response.text
    assert "llm-summary-secret" not in rendered
    assert "raw group text must not leak" not in rendered
    assert "raw update body must not leak" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered


async def test_get_summaries_filters_and_paginates(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        job, group = await _seed_summary(session, secret_service)

    app = _web_app(session_factory, bootstrap_config)
    filtered = await _request(app, "GET", f"/api/summaries?status=succeeded&group_id={group.id}&q=Summary")
    first_page = await _request(app, "GET", "/api/summaries?limit=1")

    assert filtered.status_code == 200
    assert [item["job_id"] for item in filtered.json()["items"]] == [job.id]
    assert first_page.status_code == 200
    assert first_page.json()["items"]


async def test_summaries_api_requires_admin_token(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "GET",
        "/api/summaries",
        token=None,
    )

    assert response.status_code == 401
