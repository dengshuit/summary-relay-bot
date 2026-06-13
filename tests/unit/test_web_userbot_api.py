from __future__ import annotations

from dataclasses import dataclass

import httpx
from sqlalchemy import select

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.db.models import AuditLog, SummaryUserbot
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.userbot_auth import create_summary_userbot
from summary_relay_bot.telegram.userbot import (
    UserbotAuthResult,
    UserbotClientConfig,
    UserbotIdentity,
    UserbotPasswordRequired,
)
from summary_relay_bot.web.app import create_web_app


ADMIN_TOKEN = "webui-admin-secret"


def _bootstrap_config() -> BootstrapConfig:
    return BootstrapConfig(
        database_url="sqlite+aiosqlite:///:memory:",
        settings_encryption_key=SecretService.generate_key(),
        webui_admin_token=ADMIN_TOKEN,
    )


def _web_app(session_factory, bootstrap_config: BootstrapConfig, userbot_factory=None):
    app = create_web_app(
        bootstrap_config=bootstrap_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
    )
    if userbot_factory is not None:
        app.state.userbot_client_factory = userbot_factory
    return app


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


@dataclass
class FakeUserbotClient:
    config: UserbotClientConfig
    require_password: bool = False

    async def send_code(self, phone_number: str) -> str:
        return "phone-code-hash-secret"

    async def sign_in_code(
        self,
        *,
        phone_number: str,
        code: str,
        phone_code_hash: str,
    ) -> UserbotAuthResult:
        if self.require_password:
            raise UserbotPasswordRequired("partial-string-session-secret")
        return UserbotAuthResult(
            identity=UserbotIdentity(456789, "summary_user", "Summary User"),
            session_string="authorized-string-session-secret",
        )

    async def sign_in_password(self, password: str) -> UserbotAuthResult:
        return UserbotAuthResult(
            identity=UserbotIdentity(456789, "summary_user", "Summary User"),
            session_string="authorized-after-2fa-session-secret",
        )


class FakeUserbotFactory:
    def __init__(self, *, require_password: bool = False) -> None:
        self.require_password = require_password
        self.configs: list[UserbotClientConfig] = []

    def __call__(self, config: UserbotClientConfig) -> FakeUserbotClient:
        self.configs.append(config)
        return FakeUserbotClient(config=config, require_password=self.require_password)


def _assert_no_userbot_secrets(rendered: str, bootstrap_config: BootstrapConfig) -> None:
    forbidden = [
        "api-hash-secret",
        "+15550001111",
        "phone-code-hash-secret",
        "2fa-password-secret",
        "partial-string-session-secret",
        "authorized-string-session-secret",
        "authorized-after-2fa-session-secret",
        bootstrap_config.settings_encryption_key,
        ADMIN_TOKEN,
    ]
    for value in forbidden:
        assert value not in rendered


async def test_userbot_api_requires_admin_token(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "GET",
        "/api/userbot",
        token=None,
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthorized"


async def test_post_and_get_userbot_return_safe_shape(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    app = _web_app(session_factory, bootstrap_config)

    created = await _request(
        app,
        "POST",
        "/api/userbot",
        json={
            "name": " Main userbot ",
            "api_id": 12345,
            "api_hash": "api-hash-secret",
            "phone_number": "+15550001111",
            "enabled": True,
        },
    )
    fetched = await _request(app, "GET", "/api/userbot")

    assert created.status_code == 200
    assert fetched.status_code == 200
    assert created.json()["name"] == "Main userbot"
    assert created.json()["auth_status"] == "unconfigured"
    assert created.json()["runtime_status"] == "stopped"
    assert created.json()["secrets"]["api_hash"]["configured"] is True
    assert created.json()["secrets"]["phone_number"]["configured"] is True
    assert fetched.json()["active"] == created.json()["id"]
    _assert_no_userbot_secrets(created.text + fetched.text, bootstrap_config)

    service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_factory() as session:
        row = await session.get(SummaryUserbot, created.json()["id"])
        assert row is not None
        assert service.decrypt(row.api_hash_encrypted or "") == "api-hash-secret"
        audit_logs = (await session.scalars(select(AuditLog))).all()
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    _assert_no_userbot_secrets(rendered_audit, bootstrap_config)


async def test_userbot_request_validation_error_does_not_echo_secret(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/userbot",
        json={
            "name": "Invalid",
            "api_hash": "api-hash-secret",
            "phone_number": "+15550001111",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "request validation failed",
        }
    }
    _assert_no_userbot_secrets(response.text, bootstrap_config)


async def test_userbot_send_code_and_sign_in_success_redact_secrets(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    factory = FakeUserbotFactory()
    async with session_scope(session_factory) as session:
        userbot = await create_summary_userbot(
            session,
            secret_service=secret_service,
            name="Main userbot",
            api_id=12345,
            api_hash="api-hash-secret",
            phone_number="+15550001111",
            enabled=True,
        )
        userbot_id = userbot.id

    app = _web_app(session_factory, bootstrap_config, factory)
    sent = await _request(app, "POST", "/api/userbot/send-code", json={"id": userbot_id})
    signed = await _request(
        app,
        "POST",
        "/api/userbot/sign-in",
        json={"id": userbot_id, "code": "12345"},
    )

    assert sent.status_code == 200
    assert signed.status_code == 200
    assert sent.json()["auth_status"] == "code_sent"
    assert signed.json()["auth_status"] == "authorized"
    assert signed.json()["telegram_username"] == "summary_user"
    assert signed.json()["secrets"]["session"]["configured"] is True
    assert factory.configs[0].api_hash == "api-hash-secret"
    _assert_no_userbot_secrets(sent.text + signed.text, bootstrap_config)


async def test_userbot_2fa_api_flow_redacts_password_and_sessions(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    factory = FakeUserbotFactory(require_password=True)
    async with session_scope(session_factory) as session:
        userbot = await create_summary_userbot(
            session,
            secret_service=secret_service,
            name="Main userbot",
            api_id=12345,
            api_hash="api-hash-secret",
            phone_number="+15550001111",
            enabled=True,
        )
        userbot_id = userbot.id

    app = _web_app(session_factory, bootstrap_config, factory)
    await _request(app, "POST", "/api/userbot/send-code", json={"id": userbot_id})
    password_required = await _request(
        app,
        "POST",
        "/api/userbot/sign-in",
        json={"id": userbot_id, "code": "12345"},
    )
    completed = await _request(
        app,
        "POST",
        "/api/userbot/submit-password",
        json={"id": userbot_id, "password": "2fa-password-secret"},
    )

    assert password_required.status_code == 200
    assert completed.status_code == 200
    assert password_required.json()["auth_status"] == "password_required"
    assert completed.json()["auth_status"] == "authorized"
    _assert_no_userbot_secrets(password_required.text + completed.text, bootstrap_config)

    async with session_factory() as session:
        audit_logs = (await session.scalars(select(AuditLog))).all()
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    _assert_no_userbot_secrets(rendered_audit, bootstrap_config)


async def test_userbot_one_enabled_enforcement(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        first = await create_summary_userbot(
            session,
            secret_service=secret_service,
            name="First",
            api_id=12345,
            api_hash="api-hash-secret",
            phone_number="+15550001111",
            enabled=True,
        )
        second = await create_summary_userbot(
            session,
            secret_service=secret_service,
            name="Second",
            api_id=12346,
            api_hash="second-api-hash-secret",
            phone_number="+15550002222",
            enabled=False,
        )

    app = _web_app(session_factory, bootstrap_config)
    conflict = await _request(
        app,
        "POST",
        "/api/userbot",
        json={
            "name": "Third",
            "api_id": 12347,
            "api_hash": "third-api-hash-secret",
            "phone_number": "+15550003333",
            "enabled": True,
        },
    )
    switched = await _request(
        app,
        "PATCH",
        "/api/userbot",
        json={"id": second.id, "enabled": True},
    )

    assert conflict.status_code == 400
    assert conflict.json()["error"]["code"] == "validation_error"
    assert switched.status_code == 200
    async with session_factory() as session:
        first_row = await session.get(SummaryUserbot, first.id)
        second_row = await session.get(SummaryUserbot, second.id)
        assert first_row is not None
        assert second_row is not None
        assert first_row.enabled is False
        assert first_row.runtime_status == "disabled"
        assert second_row.enabled is True
