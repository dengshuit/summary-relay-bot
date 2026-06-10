from __future__ import annotations

import httpx

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.app import create_web_app


def _bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token="webui-admin-secret",
    )


def _web_app(session_factory):
    bootstrap_config = _bootstrap_config()
    return create_web_app(
        bootstrap_config=bootstrap_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
    )


async def _get_dashboard(app, headers: dict[str, str] | None = None) -> httpx.Response:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/api/dashboard", headers=headers)


async def test_dashboard_rejects_missing_token_with_uniform_401(session_factory) -> None:
    response = await _get_dashboard(_web_app(session_factory))

    assert response.status_code == 401
    assert response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "认证失败",
        }
    }


async def test_dashboard_rejects_wrong_and_malformed_tokens_with_same_response(session_factory) -> None:
    app = _web_app(session_factory)

    wrong = await _get_dashboard(app, headers={"Authorization": "Bearer close-but-wrong"})
    malformed = await _get_dashboard(app, headers={"Authorization": "Basic webui-admin-secret"})

    assert wrong.status_code == 401
    assert malformed.status_code == 401
    assert wrong.json() == malformed.json()
    rendered = wrong.text + malformed.text
    assert "webui-admin-secret" not in rendered
    assert "close-but-wrong" not in rendered
    assert "length" not in rendered.lower()


async def test_dashboard_accepts_correct_bearer_token(session_factory) -> None:
    response = await _get_dashboard(
        _web_app(session_factory),
        headers={"Authorization": "Bearer webui-admin-secret"},
    )

    assert response.status_code == 200
    assert response.json()["telegram_startup"]["status"] == "no_enabled_bot"
