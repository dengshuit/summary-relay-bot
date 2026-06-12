from __future__ import annotations

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog, GroupSummarySettings, SummaryProfile
from summary_relay_bot.db.repositories import upsert_group
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
    json: dict[str, object] | None = None,
) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.request(method, path, headers=headers, json=json)


async def test_get_summary_profiles_returns_effective_model_and_does_not_leak_provider_secret(
    session_factory,
) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-profile-secret",
            default_model="claude-default",
        )
        await create_summary_profile(
            session,
            name="Default profile",
            llm_provider=provider,
            model=None,
            prompt_version="v3",
            system_prompt="You summarize chats.",
            temperature=0.3,
            max_output_tokens=1024,
            is_default=True,
        )
        await create_summary_profile(
            session,
            name="Override profile",
            llm_provider=provider,
            model="claude-override",
            prompt_version="v4",
        )

    response = await _request(_web_app(session_factory, bootstrap_config), "GET", "/api/summary-profiles")

    assert response.status_code == 200
    payload = response.json()
    rendered = response.text
    assert [item["name"] for item in payload] == ["Default profile", "Override profile"]
    assert payload[0]["llm_provider_id"] == 1
    assert payload[0]["llm_provider_name"] == "Primary Claude"
    assert payload[0]["provider_type"] == "anthropic"
    assert payload[0]["effective_model"] == "claude-default"
    assert payload[0]["uses_provider_default_model"] is True
    assert payload[1]["effective_model"] == "claude-override"
    assert payload[1]["uses_provider_default_model"] is False
    assert "api_key" not in rendered
    assert "llm-profile-secret" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered


async def test_post_summary_profile_sets_default_exclusively_and_writes_audit(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-profile-secret",
            default_model="claude-default",
        )
        current_default = await create_summary_profile(
            session,
            name="Current default",
            llm_provider=provider,
            is_default=True,
        )
        provider_id = provider.id
        current_default_id = current_default.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/summary-profiles",
        json={
            "name": "New default",
            "llm_provider_id": provider_id,
            "model": None,
            "prompt_version": "v5",
            "temperature": 0.2,
            "max_output_tokens": 800,
            "enabled": True,
            "is_default": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["is_default"] is True
    assert payload["effective_model"] == "claude-default"
    async with session_factory() as session:
        old_default = await session.get(SummaryProfile, current_default_id)
        new_default = await session.get(SummaryProfile, payload["id"])
        assert old_default is not None
        assert new_default is not None
        assert old_default.is_default is False
        assert new_default.is_default is True
        default_count = len(
            (
                await session.scalars(
                    select(SummaryProfile).where(SummaryProfile.is_default.is_(True))
                )
            ).all()
        )
        audit_logs = (await session.scalars(select(AuditLog))).all()
    assert default_count == 1
    assert "create_summary_profile" in [log.action for log in audit_logs]
    assert "llm-profile-secret" not in str([log.redacted_after for log in audit_logs])


async def test_patch_summary_profile_updates_fields_and_model_null_uses_provider_default(
    session_factory,
) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-profile-secret",
            default_model="claude-default",
        )
        profile = await create_summary_profile(
            session,
            name="Override profile",
            llm_provider=provider,
            model="claude-override",
            prompt_version="v3",
            temperature=0.3,
            max_output_tokens=1024,
        )
        profile_id = profile.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "PATCH",
        f"/api/summary-profiles/{profile_id}",
        json={
            "name": "Updated profile",
            "model": None,
            "temperature": None,
            "max_output_tokens": None,
            "enabled": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Updated profile"
    assert payload["model"] is None
    assert payload["effective_model"] == "claude-default"
    assert payload["uses_provider_default_model"] is True
    assert payload["temperature"] is None
    assert payload["max_output_tokens"] is None
    assert payload["enabled"] is False
    async with session_factory() as session:
        profile = await session.get(SummaryProfile, profile_id)
        assert profile is not None
        assert profile.name == "Updated profile"
        assert profile.model is None
        assert profile.temperature is None
        assert profile.max_output_tokens is None
        assert profile.enabled is False
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "update_summary_profile" in audit_actions


async def test_set_default_summary_profile_enforces_single_default(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-profile-secret",
            default_model="claude-default",
        )
        first = await create_summary_profile(
            session,
            name="First",
            llm_provider=provider,
            is_default=True,
        )
        second = await create_summary_profile(
            session,
            name="Second",
            llm_provider=provider,
            is_default=False,
        )
        first_id = first.id
        second_id = second.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        f"/api/summary-profiles/{second_id}/set-default",
    )

    assert response.status_code == 200
    assert response.json()["is_default"] is True
    async with session_factory() as session:
        first = await session.get(SummaryProfile, first_id)
        second = await session.get(SummaryProfile, second_id)
        assert first is not None
        assert second is not None
        assert first.is_default is False
        assert second.is_default is True
        default_count = len(
            (
                await session.scalars(
                    select(SummaryProfile).where(SummaryProfile.is_default.is_(True))
                )
            ).all()
        )
        audit_logs = (await session.scalars(select(AuditLog))).all()
    assert default_count == 1
    assert "set_default_summary_profile" in [log.action for log in audit_logs]
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    assert "llm-profile-secret" not in rendered_audit


async def test_summary_profile_api_validates_parameters(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-profile-secret",
            default_model="claude-default",
        )
        profile = await create_summary_profile(
            session,
            name="Profile",
            llm_provider=provider,
        )
        provider_id = provider.id
        profile_id = profile.id

    app = _web_app(session_factory, bootstrap_config)
    invalid_create = await _request(
        app,
        "POST",
        "/api/summary-profiles",
        json={
            "name": "Invalid",
            "llm_provider_id": provider_id,
            "temperature": 3,
        },
    )
    invalid_update = await _request(
        app,
        "PATCH",
        f"/api/summary-profiles/{profile_id}",
        json={"max_output_tokens": 0},
    )
    missing_provider = await _request(
        app,
        "POST",
        "/api/summary-profiles",
        json={
            "name": "Missing provider",
            "llm_provider_id": 999,
        },
    )

    assert invalid_create.status_code == 400
    assert invalid_create.json()["error"]["code"] == "validation_error"
    assert invalid_update.status_code == 400
    assert invalid_update.json()["error"]["code"] == "validation_error"
    assert missing_provider.status_code == 404
    assert missing_provider.json()["error"]["code"] == "not_found"
    rendered = invalid_create.text + invalid_update.text + missing_provider.text
    assert "llm-profile-secret" not in rendered


async def test_summary_profile_api_requires_admin_token(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    get_response = await _request(app, "GET", "/api/summary-profiles", token=None)
    post_response = await _request(
        app,
        "POST",
        "/api/summary-profiles",
        token=None,
        json={
            "name": "Profile",
            "llm_provider_id": 1,
        },
    )
    patch_response = await _request(app, "PATCH", "/api/summary-profiles/1", token=None, json={})
    default_response = await _request(
        app,
        "POST",
        "/api/summary-profiles/1/set-default",
        token=None,
    )
    delete_response = await _request(app, "DELETE", "/api/summary-profiles/1", token=None)

    assert get_response.status_code == 401
    assert post_response.status_code == 401
    assert patch_response.status_code == 401
    assert default_response.status_code == 401
    assert delete_response.status_code == 401
    assert get_response.json() == post_response.json()
    assert get_response.json() == patch_response.json()
    assert get_response.json() == default_response.json()
    assert get_response.json() == delete_response.json()


async def test_delete_summary_profile_rejects_default_or_referenced_and_audits_success(
    session_factory,
) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-profile-secret",
            default_model="claude-default",
        )
        default_profile = await create_summary_profile(
            session,
            name="Default",
            llm_provider=provider,
            is_default=True,
        )
        referenced = await create_summary_profile(
            session,
            name="Referenced",
            llm_provider=provider,
        )
        unused = await create_summary_profile(
            session,
            name="Unused",
            llm_provider=provider,
        )
        group = await upsert_group(session, chat_id=-900, chat_type="group", title="Group")
        session.add(
            GroupSummarySettings(
                group_id=group.id,
                enabled=True,
                interval_minutes=30,
                summary_profile_id=referenced.id,
                timezone="UTC",
            )
        )
        default_id = default_profile.id
        referenced_id = referenced.id
        unused_id = unused.id

    app = _web_app(session_factory, bootstrap_config)
    default_conflict = await _request(app, "DELETE", f"/api/summary-profiles/{default_id}")
    referenced_conflict = await _request(app, "DELETE", f"/api/summary-profiles/{referenced_id}")
    deleted = await _request(app, "DELETE", f"/api/summary-profiles/{unused_id}")

    assert default_conflict.status_code == 409
    assert referenced_conflict.status_code == 409
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True}
    rendered = default_conflict.text + referenced_conflict.text + deleted.text
    assert "llm-profile-secret" not in rendered
    async with session_factory() as session:
        assert await session.get(SummaryProfile, unused_id) is None
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "delete_summary_profile" in audit_actions
