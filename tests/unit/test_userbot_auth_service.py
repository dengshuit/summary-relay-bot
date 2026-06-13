from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select

from summary_relay_bot.db.models import AuditLog, SummaryEntity, SummaryUserbot, SummaryUserbotAuthSession
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.userbot_auth import (
    UserbotConfigError,
    UserbotRuntimeConfig,
    create_summary_userbot,
    load_enabled_userbot_runtime_config,
    request_userbot_phone_code,
    sign_in_summary_userbot,
    submit_summary_userbot_password,
    update_summary_userbot,
)
from summary_relay_bot.telegram.userbot import (
    UserbotAuthResult,
    UserbotClientConfig,
    UserbotIdentity,
    UserbotPasswordRequired,
)


def secret_service() -> SecretService:
    return SecretService(SecretService.generate_key())


@dataclass
class FakeUserbotClient:
    config: UserbotClientConfig
    require_password: bool = False
    sent_phone: str | None = None
    signed_code: str | None = None
    signed_hash: str | None = None
    signed_password: str | None = None

    async def send_code(self, phone_number: str) -> str:
        self.sent_phone = phone_number
        return "phone-code-hash-secret"

    async def sign_in_code(
        self,
        *,
        phone_number: str,
        code: str,
        phone_code_hash: str,
    ) -> UserbotAuthResult:
        self.sent_phone = phone_number
        self.signed_code = code
        self.signed_hash = phone_code_hash
        if self.require_password:
            raise UserbotPasswordRequired("partial-string-session-secret")
        return UserbotAuthResult(
            identity=UserbotIdentity(
                telegram_user_id=123456,
                telegram_username="summary_user",
                telegram_display_name="Summary User",
            ),
            session_string="authorized-string-session-secret",
        )

    async def sign_in_password(self, password: str) -> UserbotAuthResult:
        self.signed_password = password
        return UserbotAuthResult(
            identity=UserbotIdentity(
                telegram_user_id=123456,
                telegram_username="summary_user",
                telegram_display_name="Summary User",
            ),
            session_string="authorized-after-2fa-session-secret",
        )


class FakeUserbotFactory:
    def __init__(self, *, require_password: bool = False) -> None:
        self.require_password = require_password
        self.clients: list[FakeUserbotClient] = []

    def __call__(self, config: UserbotClientConfig) -> FakeUserbotClient:
        client = FakeUserbotClient(config=config, require_password=self.require_password)
        self.clients.append(client)
        return client


async def test_create_userbot_encrypts_secrets_and_redacts_view_and_audit(db_session) -> None:
    service = secret_service()

    userbot = await create_summary_userbot(
        db_session,
        secret_service=service,
        name=" Main userbot ",
        api_id=12345,
        api_hash="api-hash-secret",
        phone_number="+15550001111",
        proxy_url="socks5://user:proxy-secret@127.0.0.1:1080",
        enabled=True,
        actor="admin",
    )

    [audit_log] = (await db_session.scalars(select(AuditLog))).all()
    assert userbot.name == "Main userbot"
    assert userbot.runtime_status == "stopped"
    assert service.decrypt(userbot.api_hash_encrypted or "") == "api-hash-secret"
    assert service.decrypt(userbot.phone_number_encrypted or "") == "+15550001111"
    assert "api-hash-secret" not in userbot.api_hash_encrypted
    assert "proxy-secret" not in userbot.proxy_url_encrypted
    assert audit_log.action == "create_summary_userbot"
    rendered_audit = str(audit_log.redacted_after)
    assert "api-hash-secret" not in rendered_audit
    assert "+15550001111" not in rendered_audit
    assert "proxy-secret" not in rendered_audit


async def test_userbot_auth_success_stores_encrypted_session_and_safe_runtime_config(db_session) -> None:
    service = secret_service()
    factory = FakeUserbotFactory()
    userbot = await create_summary_userbot(
        db_session,
        secret_service=service,
        name="Main userbot",
        api_id=12345,
        api_hash="api-hash-secret",
        phone_number="+15550001111",
        enabled=True,
    )

    sent_view = await request_userbot_phone_code(
        db_session,
        secret_service=service,
        client_factory=factory,
        userbot_id=userbot.id,
        actor="admin",
    )
    signed_view = await sign_in_summary_userbot(
        db_session,
        secret_service=service,
        client_factory=factory,
        userbot_id=userbot.id,
        code="12345",
        actor="admin",
    )

    assert sent_view.auth_status == "code_sent"
    assert signed_view.auth_status == "authorized"
    assert signed_view.runtime_status == "stopped"
    assert signed_view.telegram_username == "summary_user"
    assert factory.clients[0].config.api_hash == "api-hash-secret"
    assert factory.clients[0].sent_phone == "+15550001111"
    assert factory.clients[1].signed_code == "12345"
    assert factory.clients[1].signed_hash == "phone-code-hash-secret"
    assert signed_view.secrets.session.configured is True

    row = await db_session.get(SummaryUserbot, userbot.id)
    assert row is not None
    assert service.decrypt(row.session_encrypted or "") == "authorized-string-session-secret"
    assert "authorized-string-session-secret" not in (row.session_encrypted or "")
    auth_sessions = (await db_session.scalars(select(SummaryUserbotAuthSession))).all()
    assert [auth_session.status for auth_session in auth_sessions] == ["completed"]

    runtime = await load_enabled_userbot_runtime_config(db_session, secret_service=service)
    assert runtime is not None
    assert runtime.session_string == "authorized-string-session-secret"
    assert "authorized-string-session-secret" not in repr(runtime)
    assert "api-hash-secret" not in repr(runtime)
    assert "+15550001111" not in repr(runtime)


async def test_userbot_2fa_flow_uses_password_without_persisting_or_returning_it(db_session) -> None:
    service = secret_service()
    factory = FakeUserbotFactory(require_password=True)
    userbot = await create_summary_userbot(
        db_session,
        secret_service=service,
        name="Main userbot",
        api_id=12345,
        api_hash="api-hash-secret",
        phone_number="+15550001111",
        enabled=True,
    )
    await request_userbot_phone_code(
        db_session,
        secret_service=service,
        client_factory=factory,
        userbot_id=userbot.id,
    )

    password_required = await sign_in_summary_userbot(
        db_session,
        secret_service=service,
        client_factory=factory,
        userbot_id=userbot.id,
        code="12345",
    )
    completed = await submit_summary_userbot_password(
        db_session,
        secret_service=service,
        client_factory=factory,
        userbot_id=userbot.id,
        password="2fa-password-secret",
    )

    assert password_required.auth_status == "password_required"
    assert password_required.secrets.session.configured is True
    assert completed.auth_status == "authorized"
    assert completed.telegram_user_id == 123456
    assert factory.clients[2].config.session_string == "partial-string-session-secret"
    assert factory.clients[2].signed_password == "2fa-password-secret"

    row = await db_session.get(SummaryUserbot, userbot.id)
    assert row is not None
    assert service.decrypt(row.session_encrypted or "") == "authorized-after-2fa-session-secret"
    all_rows = str((await db_session.scalars(select(AuditLog))).all())
    assert "2fa-password-secret" not in all_rows
    assert "partial-string-session-secret" not in all_rows
    assert "authorized-after-2fa-session-secret" not in all_rows


async def test_userbot_validation_and_one_enabled_rules(db_session) -> None:
    service = secret_service()
    first = await create_summary_userbot(
        db_session,
        secret_service=service,
        name="First",
        api_id=12345,
        api_hash="first-api-hash",
        phone_number="+15550001111",
        enabled=True,
    )

    try:
        await create_summary_userbot(
            db_session,
            secret_service=service,
            name="Second",
            api_id=12346,
            api_hash="second-api-hash",
            phone_number="+15550002222",
            enabled=True,
        )
    except UserbotConfigError as exc:
        assert "only one summary userbot" in str(exc)
    else:
        raise AssertionError("second enabled userbot was accepted")

    second = await create_summary_userbot(
        db_session,
        secret_service=service,
        name="Second",
        api_id=12346,
        api_hash="second-api-hash",
        phone_number="+15550002222",
        enabled=False,
    )
    view = await update_summary_userbot(
        db_session,
        secret_service=service,
        userbot_id=second.id,
        enabled=True,
    )

    first_row = await db_session.get(SummaryUserbot, first.id)
    second_row = await db_session.get(SummaryUserbot, second.id)
    assert first_row is not None
    assert second_row is not None
    assert first_row.enabled is False
    assert first_row.runtime_status == "disabled"
    assert second_row.enabled is True
    assert view.enabled is True


async def test_enabling_new_userbot_disables_old_userbot_groups(db_session) -> None:
    service = secret_service()
    first = await create_summary_userbot(
        db_session,
        secret_service=service,
        name="First",
        api_id=12345,
        api_hash="first-api-hash",
        phone_number="+15550001111",
        session_string="first-session",
        enabled=True,
    )
    old_group = SummaryEntity(
        userbot_id=first.id,
        chat_id=-100,
        chat_type="megagroup",
        title="Old group",
        enabled=True,
        collection_status="active",
        interval_minutes=30,
    )
    db_session.add(old_group)
    await db_session.flush()
    second = await create_summary_userbot(
        db_session,
        secret_service=service,
        name="Second",
        api_id=12346,
        api_hash="second-api-hash",
        phone_number="+15550002222",
        session_string="second-session",
        enabled=False,
    )

    await update_summary_userbot(
        db_session,
        secret_service=service,
        userbot_id=second.id,
        enabled=True,
    )

    await db_session.refresh(old_group)
    assert old_group.enabled is False
    assert old_group.collection_status == "disabled"


def test_userbot_runtime_config_repr_redacts_decrypted_secrets() -> None:
    runtime = UserbotRuntimeConfig(
        userbot_id=1,
        api_id=12345,
        api_hash="api-hash-secret",
        phone_number="+15550001111",
        session_string="string-session-secret",
        proxy_url="socks5://user:proxy-secret@127.0.0.1:1080",
        name="Main userbot",
    )

    rendered = repr(runtime)
    assert "api-hash-secret" not in rendered
    assert "+15550001111" not in rendered
    assert "string-session-secret" not in rendered
    assert "proxy-secret" not in rendered
