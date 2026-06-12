from __future__ import annotations

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog, LLMProvider
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services import runtime_config
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


async def test_get_llm_providers_returns_redacted_items_and_filters(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        primary = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            base_url="https://api.anthropic.com",
            api_key="llm-primary-secret",
            default_model="claude-default",
            enabled=True,
        )
        primary.status = "valid"
        await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Backup OpenAI",
            provider_type="openai",
            api_key="llm-backup-secret",
            default_model="gpt-default",
            enabled=False,
        )

    app = _web_app(session_factory, bootstrap_config)
    response = await _request(app, "GET", "/api/llm-providers")
    filtered = await _request(app, "GET", "/api/llm-providers?enabled=true&status=valid")

    assert response.status_code == 200
    payload = response.json()
    rendered = response.text + filtered.text
    assert [item["name"] for item in payload] == ["Primary Claude", "Backup OpenAI"]
    assert payload[0]["secret"] == {"configured": True, "updated_at": None}
    assert payload[0]["models"] == ["claude-default"]
    assert filtered.status_code == 200
    assert [item["name"] for item in filtered.json()] == ["Primary Claude"]
    assert "api_key" not in rendered
    assert "llm-primary-secret" not in rendered
    assert "llm-backup-secret" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered


async def test_patch_llm_provider_secret_noop_values_do_not_modify_stored_key(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-old-secret",
            default_model="claude-default",
        )
        provider_id = provider.id
        encrypted_before = provider.api_key_encrypted

    app = _web_app(session_factory, bootstrap_config)
    payloads = [
        {},
        {"api_key": None},
        {"api_key": ""},
        {"api_key": "   \t\n"},
    ]
    for payload in payloads:
        response = await _request(app, "PATCH", f"/api/llm-providers/{provider_id}", json=payload)
        assert response.status_code == 200

    async with session_factory() as session:
        provider = await session.get(LLMProvider, provider_id)
        assert provider is not None
        assert provider.api_key_encrypted == encrypted_before
        assert secret_service.decrypt(provider.api_key_encrypted) == "llm-old-secret"
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "replace_llm_api_key" not in audit_actions


async def test_patch_llm_provider_replaces_secret_without_leaking_plaintext(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-old-secret",
            default_model="claude-default",
        )
        provider_id = provider.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "PATCH",
        f"/api/llm-providers/{provider_id}",
        json={"api_key": "llm-new-secret"},
    )

    assert response.status_code == 200
    assert response.json()["secret"]["configured"] is True
    assert response.json()["status"] == "unvalidated"
    assert "llm-old-secret" not in response.text
    assert "llm-new-secret" not in response.text
    async with session_factory() as session:
        provider = await session.get(LLMProvider, provider_id)
        assert provider is not None
        assert secret_service.decrypt(provider.api_key_encrypted) == "llm-new-secret"
        assert "llm-new-secret" not in provider.api_key_encrypted
        audit_logs = (await session.scalars(select(AuditLog))).all()
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    assert "replace_llm_api_key" in [log.action for log in audit_logs]
    assert "llm-old-secret" not in rendered_audit
    assert "llm-new-secret" not in rendered_audit


async def test_post_llm_provider_validates_parameters_and_redacts_audit(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    app = _web_app(session_factory, bootstrap_config)

    invalid = await _request(
        app,
        "POST",
        "/api/llm-providers",
        json={
            "name": "Invalid",
            "provider_type": "unknown",
            "api_key": "llm-invalid-secret",
            "default_model": "model",
        },
    )
    valid = await _request(
        app,
        "POST",
        "/api/llm-providers",
        json={
            "name": "Primary Claude",
            "provider_type": "anthropic",
            "api_key": "llm-created-secret",
            "default_model": "claude-default",
            "models": ["claude-default", "claude-3-5-sonnet-latest"],
            "timeout_seconds": 30,
            "max_retries": 2,
            "enabled": True,
        },
    )

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "validation_error"
    assert "llm-invalid-secret" not in invalid.text
    assert valid.status_code == 200
    assert valid.json()["secret"]["configured"] is True
    assert valid.json()["models"] == ["claude-default", "claude-3-5-sonnet-latest"]
    assert "llm-created-secret" not in valid.text
    async with session_factory() as session:
        audit_logs = (await session.scalars(select(AuditLog))).all()
    assert "create_llm_provider" in [log.action for log in audit_logs]
    assert "llm-created-secret" not in str([log.redacted_after for log in audit_logs])


async def test_llm_provider_request_validation_error_does_not_echo_secret(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "POST",
        "/api/llm-providers",
        json={
            "name": "Invalid",
            "provider_type": "anthropic",
            "api_key": "llm-validation-secret",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "request validation failed",
        }
    }
    assert "llm-validation-secret" not in response.text


async def test_llm_provider_test_updates_status_without_audit_or_secret_leak(
    session_factory,
    monkeypatch,
) -> None:
    async def fake_probe(provider_config: runtime_config.LLMProviderRuntimeConfig) -> None:
        assert provider_config.api_key == "llm-test-secret"

    monkeypatch.setattr(runtime_config, "probe_llm_provider", fake_probe)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-test-secret",
            default_model="claude-default",
        )
        provider_id = provider.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        f"/api/llm-providers/{provider_id}/test",
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["detail"]
    assert response.json()["status"] == "valid"
    assert "llm-test-secret" not in response.text
    async with session_factory() as session:
        provider = await session.get(LLMProvider, provider_id)
        assert provider is not None
        assert provider.status == "valid"
        assert provider.last_validated_at is not None
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "validate_llm_provider" not in audit_actions


async def test_llm_provider_api_requires_admin_token(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    get_response = await _request(app, "GET", "/api/llm-providers", token=None)
    post_response = await _request(
        app,
        "POST",
        "/api/llm-providers",
        token=None,
        json={
            "name": "Primary Claude",
            "provider_type": "anthropic",
            "api_key": "llm-secret",
            "default_model": "claude-default",
        },
    )
    patch_response = await _request(app, "PATCH", "/api/llm-providers/1", token=None, json={})
    test_response = await _request(app, "POST", "/api/llm-providers/1/test", token=None)
    models_response = await _request(app, "GET", "/api/llm-providers/1/models", token=None)
    fetch_models_response = await _request(
        app,
        "POST",
        "/api/llm-providers/fetch-models",
        token=None,
        json={"provider_type": "anthropic"},
    )
    delete_response = await _request(app, "DELETE", "/api/llm-providers/1", token=None)

    assert get_response.status_code == 401
    assert post_response.status_code == 401
    assert patch_response.status_code == 401
    assert test_response.status_code == 401
    assert models_response.status_code == 401
    assert fetch_models_response.status_code == 401
    assert delete_response.status_code == 401
    assert get_response.json() == post_response.json()
    assert get_response.json() == patch_response.json()
    assert get_response.json() == test_response.json()
    assert get_response.json() == models_response.json()
    assert get_response.json() == fetch_models_response.json()
    assert get_response.json() == delete_response.json()
    assert "llm-secret" not in post_response.text


async def test_provider_models_can_be_replaced_and_default_must_be_included(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Primary Claude",
            provider_type="anthropic",
            api_key="llm-model-secret",
            default_model="claude-default",
        )
        provider_id = provider.id

    app = _web_app(session_factory, bootstrap_config)
    invalid = await _request(
        app,
        "PATCH",
        f"/api/llm-providers/{provider_id}",
        json={"models": ["claude-other"]},
    )
    valid = await _request(
        app,
        "PATCH",
        f"/api/llm-providers/{provider_id}",
        json={"models": ["claude-default", "claude-other"]},
    )
    models = await _request(app, "GET", f"/api/llm-providers/{provider_id}/models")

    assert invalid.status_code == 400
    assert invalid.json()["error"]["code"] == "validation_error"
    assert valid.status_code == 200
    assert valid.json()["models"] == ["claude-default", "claude-other"]
    assert models.status_code == 200
    assert models.json() == {"success": True, "models": ["claude-default", "claude-other"]}
    rendered = invalid.text + valid.text + models.text
    assert "llm-model-secret" not in rendered


async def test_fetch_models_anthropic_returns_presets_without_leaking_temporary_key(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "POST",
        "/api/llm-providers/fetch-models",
        json={"provider_type": "anthropic", "api_key": "llm-temporary-secret"},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["source"] == "preset"
    assert response.json()["models"]
    assert "llm-temporary-secret" not in response.text


async def test_delete_llm_provider_rejects_referenced_and_audits_success(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        used = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Used provider",
            provider_type="anthropic",
            api_key="llm-used-secret",
            default_model="claude-default",
        )
        unused = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Unused provider",
            provider_type="anthropic",
            api_key="llm-unused-secret",
            default_model="claude-default",
        )
        await create_summary_profile(session, name="Profile", llm_provider=used)
        used_id = used.id
        unused_id = unused.id

    app = _web_app(session_factory, bootstrap_config)
    conflict = await _request(app, "DELETE", f"/api/llm-providers/{used_id}")
    deleted = await _request(app, "DELETE", f"/api/llm-providers/{unused_id}")

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"
    assert deleted.status_code == 200
    assert deleted.json() == {"success": True}
    rendered = conflict.text + deleted.text
    assert "llm-used-secret" not in rendered
    assert "llm-unused-secret" not in rendered
    async with session_factory() as session:
        assert await session.get(LLMProvider, unused_id) is None
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "delete_llm_provider" in audit_actions
