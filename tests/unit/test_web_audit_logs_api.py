from __future__ import annotations

from datetime import timedelta

import httpx

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog, utcnow
from summary_relay_bot.db.session import session_scope
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


async def test_audit_logs_filter_paginate_and_redact_response(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    now = utcnow()
    async with session_scope(session_factory) as session:
        old = AuditLog(
            actor="webui_admin",
            action="update_group_summary_settings",
            entity_type="group_summary_settings",
            entity_id="1",
            redacted_before={"enabled": False},
            redacted_after={"enabled": True},
            created_at=now - timedelta(days=2),
        )
        first = AuditLog(
            actor="webui_admin",
            action="trigger_summary",
            entity_type="summary_job",
            entity_id="10",
            redacted_before=None,
            redacted_after={
                "job_id": 10,
                "api_key": "llm-audit-secret",
                "nested": {"bot_token": "123456:bot-secret"},
            },
            created_at=now - timedelta(minutes=2),
        )
        second = AuditLog(
            actor="webui_admin",
            action="trigger_summary",
            entity_type="summary_job",
            entity_id="11",
            redacted_before=None,
            redacted_after={"job_id": 11},
            created_at=now - timedelta(minutes=1),
        )
        session.add_all([old, first, second])

    app = _web_app(session_factory, bootstrap_config)
    filtered = await _request(
        app,
        "GET",
        f"/api/audit-logs?entity_type=summary_job&action=trigger_summary&from={(now - timedelta(hours=1)).isoformat()}&limit=1",
    )
    assert filtered.status_code == 200
    payload = filtered.json()
    assert [item["entity_id"] for item in payload["items"]] == ["11"]
    assert payload["next_cursor"] is not None

    next_page = await _request(app, "GET", f"/api/audit-logs?limit=1&cursor={payload['next_cursor']}")
    assert next_page.status_code == 200
    assert next_page.json()["items"][0]["entity_id"] == "10"
    rendered = filtered.text + next_page.text
    assert "llm-audit-secret" not in rendered
    assert "bot-secret" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered
    assert first.entity_id == "10"
    assert second.entity_id == "11"


async def test_audit_logs_reject_invalid_cursor(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "GET",
        "/api/audit-logs?cursor=not-an-int",
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


async def test_audit_logs_api_requires_admin_token(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "GET",
        "/api/audit-logs",
        token=None,
    )

    assert response.status_code == 401
