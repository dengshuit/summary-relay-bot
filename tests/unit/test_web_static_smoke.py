from __future__ import annotations

from pathlib import Path

import httpx

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.app import create_web_app


ADMIN_TOKEN = "webui-admin-secret"


def _bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token=ADMIN_TOKEN,
    )


def _write_dist(static_dir: Path) -> None:
    assets_dir = static_dir / "assets"
    assets_dir.mkdir(parents=True)
    (static_dir / "index.html").write_text(
        '<!doctype html><html><head><script type="module" src="/assets/app.js"></script></head>'
        '<body><div id="root"></div></body></html>',
        encoding="utf-8",
    )
    (assets_dir / "app.js").write_text("window.__WEBUI_SMOKE__ = true;\n", encoding="utf-8")


def _web_app(session_factory, static_dir: Path):
    bootstrap_config = _bootstrap_config()
    return create_web_app(
        bootstrap_config=bootstrap_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
        static_dir=static_dir,
    )


async def _get(app, path: str, *, token: str | None = None) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get(path, headers=headers)


async def _post(app, path: str, *, token: str | None = ADMIN_TOKEN) -> httpx.Response:
    headers = {"Authorization": f"Bearer {token}"} if token is not None else None
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.post(path, headers=headers)


async def test_static_index_api_auth_and_spa_fallback_smoke(tmp_path, session_factory) -> None:
    static_dir = tmp_path / "dist"
    _write_dist(static_dir)
    app = _web_app(session_factory, static_dir)

    index_response = await _get(app, "/")
    api_response = await _get(app, "/api/dashboard")
    missing_api_post_response = await _post(app, "/api/system/restart")
    fallback_response = await _get(app, "/groups/123")
    asset_response = await _get(app, "/assets/app.js")

    assert index_response.status_code == 200
    assert 'src="/assets/app.js"' in index_response.text
    assert ADMIN_TOKEN not in index_response.text

    assert api_response.status_code == 401
    assert api_response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "认证失败",
        }
    }

    assert missing_api_post_response.status_code == 404

    assert fallback_response.status_code == 200
    assert fallback_response.text == index_response.text

    assert asset_response.status_code == 200
    assert "WEBUI_SMOKE" in asset_response.text
