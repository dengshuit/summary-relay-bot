from __future__ import annotations

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.telegram_runtime import RuntimeBusyError
from summary_relay_bot.web.app import create_web_app


ADMIN_TOKEN = "webui-admin-secret"


def _bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token=ADMIN_TOKEN,
    )


def _web_app(session_factory, bootstrap_config: BootstrapConfig, telegram_runtime=None):
    return create_web_app(
        bootstrap_config=bootstrap_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
        telegram_runtime=telegram_runtime,
    )


class SuccessfulRuntime:
    def __init__(self) -> None:
        self.reloads = 0

    async def reload_from_db(self) -> None:
        self.reloads += 1


class BusyRuntime:
    async def reload_from_db(self) -> None:
        raise RuntimeBusyError("busy")


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


async def test_reload_bot_runtime_success_writes_audit(session_factory) -> None:
    runtime = SuccessfulRuntime()
    bootstrap_config = _bootstrap_config()
    response = await _request(
        _web_app(session_factory, bootstrap_config, runtime),
        "POST",
        "/api/system/reload-bot-runtime",
    )

    assert response.status_code == 200
    assert response.json() == {
        "accepted": True,
        "status": "accepted",
        "detail": "Bot runtime reload completed",
    }
    assert runtime.reloads == 1
    async with session_factory() as session:
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "reload_bot_runtime" in audit_actions


async def test_reload_bot_runtime_busy_or_unavailable(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    busy = await _request(
        _web_app(session_factory, bootstrap_config, BusyRuntime()),
        "POST",
        "/api/system/reload-bot-runtime",
    )
    unavailable = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/system/reload-bot-runtime",
    )
    restart = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/system/restart",
    )

    assert busy.status_code == 409
    assert busy.json()["error"]["code"] == "runtime_busy"
    assert unavailable.status_code == 409
    assert unavailable.json()["error"]["code"] == "runtime_unavailable"
    assert restart.status_code == 404


async def test_system_api_requires_admin_token(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config(), SuccessfulRuntime()),
        "POST",
        "/api/system/reload-bot-runtime",
        token=None,
    )

    assert response.status_code == 401
