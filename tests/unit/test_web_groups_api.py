from __future__ import annotations

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog, GroupSummarySettings
from summary_relay_bot.db.repositories import upsert_group
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    create_llm_provider,
    create_summary_profile,
    load_summary_profile_runtime_config,
    set_group_summary_settings,
)
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
    json: dict[str, object] | None = None,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers, json=json)


async def _seed_provider_and_profiles(session, secret_service: SecretService):
    provider = await create_llm_provider(
        session,
        secret_service=secret_service,
        name="Primary Claude",
        provider_type="anthropic",
        api_key="llm-groups-secret",
        default_model="claude-default",
    )
    default_profile = await create_summary_profile(
        session,
        name="Default profile",
        llm_provider=provider,
        model=None,
        is_default=True,
    )
    group_profile = await create_summary_profile(
        session,
        name="Group profile",
        llm_provider=provider,
        model="claude-group",
    )
    return default_profile, group_profile


async def test_get_groups_and_detail_are_read_only_and_redacted(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        default_profile, group_profile = await _seed_provider_and_profiles(session, secret_service)
        group = await upsert_group(
            session,
            chat_id=-100123,
            chat_type="supergroup",
            title="技术交流群",
            username="tech_group",
        )
        await set_group_summary_settings(
            session,
            group=group,
            enabled=True,
            interval_minutes=30,
            summary_profile=group_profile,
            timezone="Asia/Shanghai",
        )
        initial_audit_count = len((await session.scalars(select(AuditLog))).all())
        group_id = group.id

    app = _web_app(session_factory, bootstrap_config)
    list_response = await _request(app, "GET", "/api/groups")
    detail_response = await _request(app, "GET", f"/api/groups/{group_id}")

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
    payload = list_response.json()
    detail = detail_response.json()
    rendered = list_response.text + detail_response.text
    assert payload["items"][0]["title"] == "技术交流群"
    assert payload["items"][0]["settings"] == {
        "enabled": True,
        "interval_minutes": 30,
        "summary_profile_id": group_profile.id,
        "timezone": "Asia/Shanghai",
    }
    assert payload["items"][0]["effective_profile"] == {
        "id": group_profile.id,
        "name": "Group profile",
        "model": "claude-group",
        "provider": "Primary Claude",
    }
    assert detail["summary_state"]["last_summary_sequence"] == 0
    assert detail["active_job"] is None
    assert detail["recent_jobs"] == []
    assert default_profile.is_default is True
    assert "llm-groups-secret" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered
    async with session_factory() as session:
        audit_count = len((await session.scalars(select(AuditLog))).all())
    assert audit_count == initial_audit_count


async def test_patch_group_summary_settings_validates_and_allows_null_profile(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        default_profile, group_profile = await _seed_provider_and_profiles(session, secret_service)
        group = await upsert_group(session, chat_id=-200, chat_type="group", title="Group")
        await set_group_summary_settings(
            session,
            group=group,
            enabled=True,
            interval_minutes=30,
            summary_profile=group_profile,
        )
        group_id = group.id

    app = _web_app(session_factory, bootstrap_config)
    invalid = await _request(
        app,
        "PATCH",
        f"/api/groups/{group_id}/summary-settings",
        json={
            "enabled": True,
            "interval_minutes": 0,
            "summary_profile_id": group_profile.id,
            "timezone": "UTC",
        },
    )
    null_profile = await _request(
        app,
        "PATCH",
        f"/api/groups/{group_id}/summary-settings",
        json={
            "enabled": False,
            "interval_minutes": 45,
            "summary_profile_id": None,
            "timezone": "UTC",
        },
    )

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "validation_error"
    assert null_profile.status_code == 200
    assert null_profile.json()["settings"] == {
        "enabled": False,
        "interval_minutes": 45,
        "summary_profile_id": None,
        "timezone": "UTC",
    }
    assert null_profile.json()["id"] == group_id
    assert null_profile.json()["effective_profile"]["id"] == default_profile.id
    async with session_factory() as session:
        group = await upsert_group(session, chat_id=-200, chat_type="group", title="Group")
        settings = await session.scalar(
            select(GroupSummarySettings).where(GroupSummarySettings.group_id == group.id)
        )
        runtime = await load_summary_profile_runtime_config(
            session,
            secret_service=secret_service,
            group=group,
        )
        audit_logs = (await session.scalars(select(AuditLog))).all()

    assert settings is not None
    assert settings.summary_profile_id is None
    assert runtime.summary_profile_id == default_profile.id
    assert "update_group_summary_settings" in [log.action for log in audit_logs]
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    assert "llm-groups-secret" not in rendered_audit


async def test_groups_api_requires_admin_token(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    list_response = await _request(app, "GET", "/api/groups", token=None)
    detail_response = await _request(app, "GET", "/api/groups/1", token=None)
    patch_response = await _request(
        app,
        "PATCH",
        "/api/groups/1/summary-settings",
        token=None,
        json={"enabled": True, "interval_minutes": 30, "summary_profile_id": None},
    )

    assert list_response.status_code == 401
    assert detail_response.status_code == 401
    assert patch_response.status_code == 401
    assert list_response.json() == detail_response.json()
    assert list_response.json() == patch_response.json()
