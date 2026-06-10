from __future__ import annotations

import httpx

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    create_bot_instance,
    create_llm_provider,
    create_summary_profile,
)
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.app import create_web_app


def _bootstrap_config(*, admin_token: str = "webui-admin-secret") -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token=admin_token,
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


async def _dashboard_json(app, *, token: str = "webui-admin-secret") -> dict[str, object]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/api/dashboard", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    return response.json()


async def test_dashboard_returns_empty_database_state(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    payload = await _dashboard_json(app)

    assert payload == {
        "telegram_startup": {
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
        "bot": None,
        "groups": {
            "total": 0,
            "enabled": 0,
        },
        "default_profile": None,
        "summary_24h": {
            "total": 0,
            "succeeded": 0,
            "failed": 0,
        },
        "restart_pending": [],
        "recent_audit_logs": [],
    }


async def test_dashboard_response_does_not_leak_secrets(session_factory) -> None:
    bootstrap_config = _bootstrap_config(admin_token="webui-admin-secret")
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:bot-secret",
            owner_id=3003,
            enabled=True,
        )
        provider = await create_llm_provider(
            session,
            secret_service=secret_service,
            name="Anthropic",
            provider_type="anthropic",
            api_key="llm-api-secret",
            default_model="claude-default",
        )
        await create_summary_profile(
            session,
            name="Default profile",
            llm_provider=provider,
            is_default=True,
        )
        session.add(
            AuditLog(
                actor="webui_admin",
                action="replace_secret",
                entity_type="llm_provider",
                entity_id=str(provider.id),
                redacted_before={"api_key": "llm-api-secret"},
                redacted_after={"bot_token": "123456:bot-secret"},
            )
        )

    app = _web_app(session_factory, bootstrap_config)

    payload = await _dashboard_json(app)
    rendered = str(payload)

    assert payload["bot"] is not None
    assert "owner_id" not in rendered
    assert "3003" not in rendered
    assert "webui-admin-secret" not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered
    assert "bot-secret" not in rendered
    assert "llm-api-secret" not in rendered
