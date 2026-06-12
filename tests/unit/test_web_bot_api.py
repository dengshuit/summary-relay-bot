from __future__ import annotations

import httpx
from aiohttp_socks import ProxyConnectionError
from aiogram.exceptions import TelegramNetworkError
from sqlalchemy import select

from summary_relay_bot.config import AppConfig, BootstrapConfig
from summary_relay_bot.db.models import AuditLog, BotInstance
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services import runtime_config
from summary_relay_bot.services.runtime_config import (
    clear_bot_restart_flags,
    create_bot_instance,
    get_bot_instance_view,
)
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


def _web_app(
    session_factory,
    bootstrap_config: BootstrapConfig,
    app_config: AppConfig | None = None,
):
    return create_web_app(
        bootstrap_config=bootstrap_config,
        app_config=app_config,
        session_factory=session_factory,
        secret_service=SecretService(bootstrap_config.settings_encryption_key),
        telegram_startup={
            "status": "no_enabled_bot",
            "detail": "no enabled bot instance is configured",
        },
    )


def _web_app_with_runtime(session_factory, bootstrap_config: BootstrapConfig, telegram_runtime):
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


class BusyRuntime:
    async def reload_after_change(self, change):
        raise RuntimeBusyError("busy")


class SuccessfulRuntime:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory
        self.reloads = 0

    async def reload_after_change(self, change):
        self.reloads += 1
        async with session_scope(self.session_factory) as session:
            bot = await change(session)
            await clear_bot_restart_flags(session, bot_instance_ids=None)
        async with self.session_factory() as session:
            return await get_bot_instance_view(session, bot.id)


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


async def test_get_bot_returns_redacted_active_and_items(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:main-secret",
            owner_id=8812345678,
            enabled=True,
        )
        await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Backup bot",
            bot_token="123456:backup-secret",
            owner_id=9912345678,
            enabled=False,
        )

    response = await _request(_web_app(session_factory, bootstrap_config), "GET", "/api/bot")

    assert response.status_code == 200
    payload = response.json()
    rendered = response.text
    assert payload["active"] == 1
    assert [item["name"] for item in payload["items"]] == ["Main bot", "Backup bot"]
    assert payload["items"][0]["owner_id_redacted"] == "88***78"
    assert payload["items"][0]["secret"]["configured"] is True
    assert "bot_token" not in rendered
    assert "main-secret" not in rendered
    assert "backup-secret" not in rendered
    assert "8812345678" not in rendered
    assert ADMIN_TOKEN not in rendered
    assert bootstrap_config.settings_encryption_key not in rendered


async def test_post_bot_creates_redacted_enabled_instance(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    app = _web_app(session_factory, bootstrap_config)

    response = await _request(
        app,
        "POST",
        "/api/bot",
        json={
            "name": " Main bot ",
            "bot_token": "123456:created-secret",
            "owner_id": 8812345678,
            "enabled": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["name"] == "Main bot"
    assert payload["enabled"] is True
    assert payload["owner_id_redacted"] == "88***78"
    assert payload["secret"] == {"configured": True, "updated_at": None}
    assert "123456:created-secret" not in response.text
    assert "8812345678" not in response.text
    assert ADMIN_TOKEN not in response.text
    assert bootstrap_config.settings_encryption_key not in response.text

    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_factory() as session:
        bots = (await session.scalars(select(BotInstance))).all()
        audit_logs = (await session.scalars(select(AuditLog))).all()
    assert len(bots) == 1
    assert secret_service.decrypt(bots[0].bot_token_encrypted) == "123456:created-secret"
    assert "create_bot_instance" in [log.action for log in audit_logs]
    assert "created-secret" not in str([log.redacted_after for log in audit_logs])


async def test_post_bot_validates_parameters_without_leaking_secret(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "POST",
        "/api/bot",
        json={
            "name": "Invalid bot",
            "bot_token": "123456:invalid-secret",
            "owner_id": 0,
            "enabled": True,
        },
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert "invalid-secret" not in response.text


async def test_bot_request_validation_error_does_not_echo_secret(session_factory) -> None:
    response = await _request(
        _web_app(session_factory, _bootstrap_config()),
        "POST",
        "/api/bot",
        json={
            "name": "Invalid bot",
            "bot_token": "123456:validation-secret",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "error": {
            "code": "validation_error",
            "message": "request validation failed",
        }
    }
    assert "validation-secret" not in response.text


async def test_patch_bot_secret_noop_values_do_not_modify_stored_token(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:main-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id
        encrypted_before = bot.bot_token_encrypted

    app = _web_app(session_factory, bootstrap_config)
    payloads = [
        {"id": bot_id},
        {"id": bot_id, "bot_token": None},
        {"id": bot_id, "bot_token": ""},
        {"id": bot_id, "bot_token": "   \t\n"},
    ]
    for payload in payloads:
        response = await _request(app, "PATCH", "/api/bot", json=payload)
        assert response.status_code == 200

    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.bot_token_encrypted == encrypted_before
        assert secret_service.decrypt(bot.bot_token_encrypted) == "123456:main-secret"
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "replace_bot_token" not in audit_actions


async def test_patch_bot_replaces_secret_without_leaking_plaintext(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:old-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "PATCH",
        "/api/bot",
        json={"id": bot_id, "bot_token": "123456:new-secret"},
    )

    assert response.status_code == 200
    rendered_response = response.text
    assert response.json()["needs_restart"] is True
    assert response.json()["secret"]["configured"] is True
    assert "old-secret" not in rendered_response
    assert "new-secret" not in rendered_response
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert secret_service.decrypt(bot.bot_token_encrypted) == "123456:new-secret"
        assert "new-secret" not in bot.bot_token_encrypted
        audit_logs = (await session.scalars(select(AuditLog))).all()
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    assert "replace_bot_token" in [log.action for log in audit_logs]
    assert "old-secret" not in rendered_audit
    assert "new-secret" not in rendered_audit


async def test_patch_bot_reload_required_busy_returns_409_without_committing(
    session_factory,
) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:old-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id
        encrypted_before = bot.bot_token_encrypted

    response = await _request(
        _web_app_with_runtime(session_factory, bootstrap_config, BusyRuntime()),
        "PATCH",
        "/api/bot",
        json={"id": bot_id, "bot_token": "123456:new-secret"},
    )

    assert response.status_code == 409
    assert response.json() == {
        "error": {
            "code": "runtime_busy",
            "message": "Bot runtime reload is blocked by an active summary; retry after it finishes",
        }
    }
    assert "old-secret" not in response.text
    assert "new-secret" not in response.text
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.bot_token_encrypted == encrypted_before
        assert secret_service.decrypt(bot.bot_token_encrypted) == "123456:old-secret"
        assert bot.needs_restart is False


async def test_patch_bot_reload_success_clears_restart_flag(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:old-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id
    runtime = SuccessfulRuntime(session_factory)

    response = await _request(
        _web_app_with_runtime(session_factory, bootstrap_config, runtime),
        "PATCH",
        "/api/bot",
        json={"id": bot_id, "owner_id": 9988776655},
    )

    assert response.status_code == 200
    assert response.json()["needs_restart"] is False
    assert response.json()["owner_id_redacted"] == "99***55"
    assert runtime.reloads == 1
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.owner_id == 9988776655
        assert bot.needs_restart is False


async def test_patch_bot_owner_id_marks_restart_and_redacts_audit(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:main-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "PATCH",
        "/api/bot",
        json={"id": bot_id, "owner_id": 9988776655},
    )

    assert response.status_code == 200
    rendered_response = response.text
    assert response.json()["needs_restart"] is True
    assert response.json()["owner_id_redacted"] == "99***55"
    assert "9988776655" not in rendered_response
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.owner_id == 9988776655
        assert bot.needs_restart is True
        audit_logs = (await session.scalars(select(AuditLog))).all()
    rendered_audit = str([log.redacted_before for log in audit_logs]) + str(
        [log.redacted_after for log in audit_logs]
    )
    assert "update_bot_instance" in [log.action for log in audit_logs]
    assert "9988776655" not in rendered_audit
    assert "main-secret" not in rendered_audit


async def test_patch_bot_name_updates_without_marking_restart(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:main-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "PATCH",
        "/api/bot",
        json={"id": bot_id, "name": "Production bot"},
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Production bot"
    assert response.json()["needs_restart"] is False
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.name == "Production bot"
        assert bot.needs_restart is False
        audit_logs = (await session.scalars(select(AuditLog))).all()
    assert "update_bot_instance" in [log.action for log in audit_logs]
    assert "main-secret" not in str([log.redacted_after for log in audit_logs])


async def test_validate_bot_updates_status_without_audit_log(session_factory, monkeypatch) -> None:
    async def fake_fetch_bot_identity(
        bot_token: str,
        *,
        telegram_api_proxy: str | None = None,
    ) -> runtime_config.BotIdentity:
        assert bot_token == "123456:main-secret"
        assert telegram_api_proxy is None
        return runtime_config.BotIdentity(
            telegram_bot_id=7654321098,
            telegram_username="summary_relay_bot",
        )

    monkeypatch.setattr(runtime_config, "fetch_bot_identity", fake_fetch_bot_identity)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:main-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/bot/validate",
        json={"id": bot_id, "bot_token": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["detail"]
    assert payload["status"] == "valid"
    assert payload["bot_id"] == 7654321098
    assert payload["username"] == "summary_relay_bot"
    assert "main-secret" not in response.text
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.status == "valid"
        assert bot.last_validated_at is not None
        assert bot.telegram_bot_id == 7654321098
        assert bot.telegram_username == "summary_relay_bot"
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "validate_bot_instance" not in audit_actions


async def test_validate_bot_with_non_empty_token_does_not_replace_stored_secret(
    session_factory,
    monkeypatch,
) -> None:
    async def fake_fetch_bot_identity(
        bot_token: str,
        *,
        telegram_api_proxy: str | None = None,
    ) -> runtime_config.BotIdentity:
        assert bot_token == "123456:temporary-secret"
        assert telegram_api_proxy is None
        return runtime_config.BotIdentity(
            telegram_bot_id=123456,
            telegram_username="temporary_bot",
        )

    monkeypatch.setattr(runtime_config, "fetch_bot_identity", fake_fetch_bot_identity)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:stored-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id
        encrypted_before = bot.bot_token_encrypted

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/bot/validate",
        json={"id": bot_id, "bot_token": "123456:temporary-secret"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "valid"
    assert "temporary-secret" not in response.text
    assert "stored-secret" not in response.text
    async with session_factory() as session:
        bot = await session.get(BotInstance, bot_id)
        assert bot is not None
        assert bot.bot_token_encrypted == encrypted_before
        assert secret_service.decrypt(bot.bot_token_encrypted) == "123456:stored-secret"
        assert bot.status == "unvalidated"
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert "replace_bot_token" not in audit_actions


async def test_validate_bot_classifies_telegram_network_errors(
    session_factory,
    monkeypatch,
) -> None:
    async def fake_fetch_bot_identity(
        bot_token: str,
        *,
        telegram_api_proxy: str | None = None,
    ) -> runtime_config.BotIdentity:
        assert telegram_api_proxy is None
        raise TelegramNetworkError(method="getMe", message="connection failed")

    monkeypatch.setattr(runtime_config, "fetch_bot_identity", fake_fetch_bot_identity)
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:stored-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "POST",
        "/api/bot/validate",
        json={"id": bot_id, "bot_token": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["error_type"] == "telegram_transient"
    assert payload["error_message"] == "Telegram API is temporarily unreachable"
    assert payload["detail"] == "Telegram API is temporarily unreachable"
    assert "stored-secret" not in response.text


async def test_validate_bot_classifies_proxy_errors(
    session_factory,
    monkeypatch,
) -> None:
    async def fake_fetch_bot_identity(
        bot_token: str,
        *,
        telegram_api_proxy: str | None = None,
    ) -> runtime_config.BotIdentity:
        assert telegram_api_proxy == "socks5://127.0.0.1:1"
        raise ProxyConnectionError("proxy connection failed")

    monkeypatch.setattr(runtime_config, "fetch_bot_identity", fake_fetch_bot_identity)
    bootstrap_config = _bootstrap_config()
    app_config = AppConfig.from_bootstrap_runtime(
        bootstrap_config,
        env={"TELEGRAM_API_PROXY": "socks5://127.0.0.1:1"},
    )
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:stored-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config, app_config=app_config),
        "POST",
        "/api/bot/validate",
        json={"id": bot_id, "bot_token": None},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is False
    assert payload["status"] == "error"
    assert payload["error_type"] == "telegram_transient"
    assert payload["error_message"] == "Telegram API is temporarily unreachable"
    assert "stored-secret" not in response.text
    assert "127.0.0.1:1" not in response.text


async def test_validate_bot_passes_configured_telegram_proxy(
    session_factory,
    monkeypatch,
) -> None:
    observed: dict[str, str | None] = {}

    async def fake_fetch_bot_identity(
        bot_token: str,
        *,
        telegram_api_proxy: str | None = None,
    ) -> runtime_config.BotIdentity:
        observed["token"] = bot_token
        observed["proxy"] = telegram_api_proxy
        return runtime_config.BotIdentity(
            telegram_bot_id=7654321098,
            telegram_username="summary_relay_bot",
        )

    monkeypatch.setattr(runtime_config, "fetch_bot_identity", fake_fetch_bot_identity)
    bootstrap_config = _bootstrap_config()
    app_config = AppConfig.from_bootstrap_runtime(
        bootstrap_config,
        env={"TELEGRAM_API_PROXY": "socks5://127.0.0.1:7890"},
    )
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        bot = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Main bot",
            bot_token="123456:stored-secret",
            owner_id=1001,
            enabled=True,
        )
        bot_id = bot.id

    response = await _request(
        _web_app(session_factory, bootstrap_config, app_config=app_config),
        "POST",
        "/api/bot/validate",
        json={"id": bot_id, "bot_token": None},
    )

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert observed == {
        "token": "123456:stored-secret",
        "proxy": "socks5://127.0.0.1:7890",
    }
    assert "stored-secret" not in response.text
    assert "127.0.0.1:7890" not in response.text


async def test_patch_bot_enabled_enforces_single_enabled_bot(session_factory) -> None:
    bootstrap_config = _bootstrap_config()
    secret_service = SecretService(bootstrap_config.settings_encryption_key)
    async with session_scope(session_factory) as session:
        first = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="First bot",
            bot_token="123456:first-secret",
            owner_id=1001,
            enabled=True,
        )
        second = await create_bot_instance(
            session,
            secret_service=secret_service,
            name="Second bot",
            bot_token="123456:second-secret",
            owner_id=1002,
            enabled=False,
        )
        first_id = first.id
        second_id = second.id

    response = await _request(
        _web_app(session_factory, bootstrap_config),
        "PATCH",
        "/api/bot",
        json={"id": second_id, "enabled": True},
    )

    assert response.status_code == 200
    assert response.json()["enabled"] is True
    assert response.json()["needs_restart"] is True
    async with session_factory() as session:
        first = await session.get(BotInstance, first_id)
        second = await session.get(BotInstance, second_id)
        assert first is not None
        assert second is not None
        assert first.enabled is False
        assert first.needs_restart is True
        assert second.enabled is True
        assert second.needs_restart is True
        enabled_count = len(
            (
                await session.scalars(
                    select(BotInstance).where(BotInstance.enabled.is_(True))
                )
            ).all()
        )
        audit_actions = [row.action for row in (await session.scalars(select(AuditLog))).all()]
    assert enabled_count == 1
    assert "enable_bot_instance" in audit_actions


async def test_bot_api_requires_admin_token(session_factory) -> None:
    app = _web_app(session_factory, _bootstrap_config())

    get_response = await _request(app, "GET", "/api/bot", token=None)
    create_response = await _request(
        app,
        "POST",
        "/api/bot",
        token=None,
        json={"name": "Main bot", "owner_id": 1, "bot_token": "123456:secret"},
    )
    validate_response = await _request(
        app,
        "POST",
        "/api/bot/validate",
        token=None,
        json={"id": 1},
    )
    patch_response = await _request(app, "PATCH", "/api/bot", token=None, json={"id": 1})

    assert get_response.status_code == 401
    assert create_response.status_code == 401
    assert validate_response.status_code == 401
    assert patch_response.status_code == 401
    assert get_response.json() == validate_response.json()
    assert get_response.json() == create_response.json()
    assert get_response.json() == patch_response.json()
    assert get_response.json() == {
        "error": {
            "code": "unauthorized",
            "message": "认证失败",
        }
    }
