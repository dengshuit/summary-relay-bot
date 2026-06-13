from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.config import redact_secret
from summary_relay_bot.db.models import SummaryEntity, SummaryUserbot, SummaryUserbotAuthSession, utcnow
from summary_relay_bot.services.runtime_config import SecretState, create_audit_log
from summary_relay_bot.services.secrets import SecretError, SecretService, redact_configured_secret
from summary_relay_bot.telegram.userbot import (
    UserbotAuthResult,
    UserbotClientConfig,
    UserbotClientError,
    UserbotClientFactory,
    UserbotPasswordRequired,
    create_telethon_userbot_client,
    parse_userbot_proxy_url,
)


class UserbotConfigError(ValueError):
    pass


class UserbotNotFoundError(UserbotConfigError):
    pass


class UserbotAuthFlowError(UserbotConfigError):
    pass


_UNSET = object()
_AUTH_SESSION_TTL = timedelta(minutes=10)
_ACTIVE_AUTH_SESSION_STATUSES = {"code_sent", "password_required"}


@dataclass(frozen=True, slots=True)
class SummaryUserbotSecretState:
    api_hash: SecretState
    phone_number: SecretState
    session: SecretState
    proxy_url: SecretState


@dataclass(frozen=True, slots=True)
class SummaryUserbotView:
    id: int
    name: str
    api_id: int | None
    phone_number_redacted: str | None
    enabled: bool
    auth_status: str
    runtime_status: str
    telegram_user_id: int | None
    telegram_username: str | None
    telegram_display_name: str | None
    last_authorized_at: datetime | None
    last_started_at: datetime | None
    last_stopped_at: datetime | None
    last_error_type: str | None
    last_error_message: str | None
    created_at: datetime
    updated_at: datetime
    secrets: SummaryUserbotSecretState


@dataclass(frozen=True, slots=True)
class UserbotRuntimeConfig:
    userbot_id: int
    api_id: int
    api_hash: str
    phone_number: str
    session_string: str
    proxy_url: str | None
    name: str

    def safe_dict(self) -> dict[str, object]:
        return {
            "userbot_id": self.userbot_id,
            "api_id": self.api_id,
            "api_hash": redact_secret(self.api_hash),
            "phone_number": "<redacted>",
            "session_string": redact_secret(self.session_string),
            "proxy_url": redact_secret(self.proxy_url),
            "name": self.name,
        }

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"UserbotRuntimeConfig({args})"


async def list_current_userbot(
    session: AsyncSession,
) -> tuple[SummaryUserbotView | None, SummaryUserbotView | None]:
    userbots = (
        await session.scalars(select(SummaryUserbot).order_by(SummaryUserbot.id))
    ).all()
    active = next((userbot for userbot in userbots if userbot.enabled), None)
    item = active or (userbots[0] if userbots else None)
    return (
        _userbot_view(active) if active is not None else None,
        _userbot_view(item) if item is not None else None,
    )


async def enabled_summary_userbot(session: AsyncSession) -> SummaryUserbot | None:
    return await session.scalar(select(SummaryUserbot).where(SummaryUserbot.enabled.is_(True)))


async def get_summary_userbot(session: AsyncSession, userbot_id: int) -> SummaryUserbot:
    userbot = await session.get(SummaryUserbot, userbot_id)
    if userbot is None:
        raise UserbotNotFoundError("summary userbot not found")
    return userbot


async def create_summary_userbot(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    name: str,
    api_id: int,
    api_hash: str,
    phone_number: str,
    proxy_url: str | None = None,
    session_string: str | None = None,
    enabled: bool = True,
    actor: str = "system",
) -> SummaryUserbot:
    normalized_name = _normalize_required_text(name, "name")
    _validate_api_id(api_id)
    normalized_api_hash = _normalize_required_text(api_hash, "api_hash")
    normalized_phone_number = _normalize_required_text(phone_number, "phone_number")
    normalized_proxy_url = _normalize_optional_secret(proxy_url)
    normalized_session_string = _normalize_optional_secret(session_string)
    if normalized_proxy_url is not None:
        _validate_proxy_url(normalized_proxy_url)
    if enabled and await enabled_summary_userbot(session) is not None:
        raise UserbotConfigError("only one summary userbot can be enabled")

    now = utcnow()
    userbot = SummaryUserbot(
        name=normalized_name,
        api_id=api_id,
        api_hash_encrypted=secret_service.encrypt(normalized_api_hash),
        phone_number_encrypted=secret_service.encrypt(normalized_phone_number),
        proxy_url_encrypted=secret_service.encrypt(normalized_proxy_url)
        if normalized_proxy_url is not None
        else None,
        session_encrypted=secret_service.encrypt(normalized_session_string)
        if normalized_session_string is not None
        else None,
        enabled=enabled,
        auth_status="authorized" if normalized_session_string is not None else "unconfigured",
        runtime_status=_runtime_status_for_enabled(enabled),
        last_authorized_at=now if normalized_session_string is not None else None,
    )
    session.add(userbot)
    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action="create_summary_userbot",
        entity_type="summary_userbot",
        entity_id=str(userbot.id),
        redacted_after=_userbot_redacted_dict(userbot),
    )
    return userbot


async def update_summary_userbot(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    userbot_id: int,
    name: str | None | object = _UNSET,
    api_id: int | None | object = _UNSET,
    api_hash: str | None | object = _UNSET,
    phone_number: str | None | object = _UNSET,
    proxy_url: str | None | object = _UNSET,
    session_string: str | None | object = _UNSET,
    enabled: bool | None | object = _UNSET,
    actor: str = "system",
) -> SummaryUserbotView:
    userbot = await get_summary_userbot(session, userbot_id)
    redacted_before = _userbot_redacted_dict(userbot)

    changed_general = False
    replaced_secret = False
    auth_reset_required = False
    session_replaced = False
    disabled_userbot_ids: list[int] = []

    if name is not _UNSET and name is not None:
        normalized_name = _normalize_required_text(name, "name")
        if normalized_name != userbot.name:
            userbot.name = normalized_name
            changed_general = True

    if api_id is not _UNSET and api_id is not None:
        _validate_api_id(api_id)
        if api_id != userbot.api_id:
            userbot.api_id = api_id
            changed_general = True
            auth_reset_required = True

    if api_hash is not _UNSET and api_hash is not None:
        normalized_api_hash = api_hash.strip()
        if normalized_api_hash != "":
            userbot.api_hash_encrypted = secret_service.encrypt(normalized_api_hash)
            replaced_secret = True
            auth_reset_required = True

    if phone_number is not _UNSET and phone_number is not None:
        normalized_phone_number = phone_number.strip()
        if normalized_phone_number != "":
            userbot.phone_number_encrypted = secret_service.encrypt(normalized_phone_number)
            replaced_secret = True
            auth_reset_required = True

    if proxy_url is not _UNSET and proxy_url is not None:
        normalized_proxy_url = proxy_url.strip()
        if normalized_proxy_url != "":
            _validate_proxy_url(normalized_proxy_url)
            userbot.proxy_url_encrypted = secret_service.encrypt(normalized_proxy_url)
            replaced_secret = True

    if session_string is not _UNSET and session_string is not None:
        normalized_session = session_string.strip()
        if normalized_session != "":
            userbot.session_encrypted = secret_service.encrypt(normalized_session)
            userbot.auth_status = "authorized"
            userbot.last_authorized_at = utcnow()
            userbot.telegram_user_id = None
            userbot.telegram_username = None
            userbot.telegram_display_name = None
            session_replaced = True
            replaced_secret = True

    if auth_reset_required:
        await _expire_active_auth_sessions(session, userbot)
        userbot.auth_status = "unconfigured"
        userbot.session_encrypted = None
        userbot.telegram_user_id = None
        userbot.telegram_username = None
        userbot.telegram_display_name = None
        userbot.last_authorized_at = None

    if enabled is not _UNSET and enabled is not None:
        if enabled:
            other_enabled = (
                await session.scalars(
                    select(SummaryUserbot)
                    .where(SummaryUserbot.enabled.is_(True))
                    .where(SummaryUserbot.id != userbot.id)
                    .order_by(SummaryUserbot.id)
                )
            ).all()
            now = utcnow()
            for other_userbot in other_enabled:
                other_userbot.enabled = False
                other_userbot.runtime_status = "disabled"
                other_userbot.updated_at = now
                await _disable_userbot_summary_entities(session, userbot_id=other_userbot.id, now=now)
                disabled_userbot_ids.append(other_userbot.id)
            if other_enabled:
                await session.flush()
            if not userbot.enabled or disabled_userbot_ids:
                changed_general = True
            userbot.enabled = True
        elif userbot.enabled:
            userbot.enabled = False
            changed_general = True
            await _disable_userbot_summary_entities(session, userbot_id=userbot.id, now=utcnow())

    if changed_general or replaced_secret or auth_reset_required or session_replaced:
        userbot.runtime_status = _runtime_status_for_enabled(userbot.enabled)
        userbot.last_error_type = None
        userbot.last_error_message = None
        userbot.updated_at = utcnow()
        await session.flush()
        redacted_after = _userbot_redacted_dict(userbot)
        if disabled_userbot_ids:
            redacted_after["disabled_userbot_ids"] = disabled_userbot_ids
        await create_audit_log(
            session,
            actor=actor,
            action="update_summary_userbot",
            entity_type="summary_userbot",
            entity_id=str(userbot.id),
            redacted_before=redacted_before,
            redacted_after=redacted_after,
        )

    return _userbot_view(userbot)


async def request_userbot_phone_code(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    client_factory: UserbotClientFactory = create_telethon_userbot_client,
    userbot_id: int | None = None,
    api_id: int | None | object = _UNSET,
    api_hash: str | None | object = _UNSET,
    phone_number: str | None | object = _UNSET,
    proxy_url: str | None | object = _UNSET,
    actor: str = "system",
) -> SummaryUserbotView:
    userbot = await _resolve_userbot(session, userbot_id)
    update_fields: dict[str, object | None] = {}
    for field_name, value in (
        ("api_id", api_id),
        ("api_hash", api_hash),
        ("phone_number", phone_number),
        ("proxy_url", proxy_url),
    ):
        if value is not _UNSET:
            update_fields[field_name] = value
    if update_fields:
        await update_summary_userbot(
            session,
            secret_service=secret_service,
            userbot_id=userbot.id,
            actor=actor,
            **update_fields,
        )
        userbot = await get_summary_userbot(session, userbot.id)

    phone = _decrypt_required(secret_service, userbot.phone_number_encrypted, "phone_number")
    config = _client_config(secret_service, userbot)
    client = client_factory(config)
    try:
        phone_code_hash = await client.send_code(phone)
    except UserbotClientError as exc:
        await _mark_userbot_auth_error(session, userbot, error_type=exc.error_type, message=str(exc))
        raise UserbotAuthFlowError(str(exc)) from exc

    await _expire_active_auth_sessions(session, userbot)
    auth_session = SummaryUserbotAuthSession(
        userbot=userbot,
        phone_code_hash_encrypted=secret_service.encrypt(phone_code_hash),
        status="code_sent",
        expires_at=utcnow() + _AUTH_SESSION_TTL,
    )
    session.add(auth_session)
    userbot.auth_status = "code_sent"
    userbot.runtime_status = _runtime_status_for_enabled(userbot.enabled)
    userbot.last_error_type = None
    userbot.last_error_message = None
    userbot.updated_at = utcnow()
    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action="send_summary_userbot_code",
        entity_type="summary_userbot",
        entity_id=str(userbot.id),
        redacted_after={
            "auth_status": userbot.auth_status,
            "auth_session_id": auth_session.id,
            "expires_at": auth_session.expires_at.isoformat(),
        },
    )
    return _userbot_view(userbot)


async def sign_in_summary_userbot(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    code: str,
    client_factory: UserbotClientFactory = create_telethon_userbot_client,
    userbot_id: int | None = None,
    actor: str = "system",
) -> SummaryUserbotView:
    normalized_code = _normalize_required_text(code, "code")
    userbot = await _resolve_userbot(session, userbot_id)
    auth_session = await _latest_auth_session(session, userbot, expected_status="code_sent")
    phone_code_hash = _decrypt_required(
        secret_service,
        auth_session.phone_code_hash_encrypted,
        "phone_code_hash",
    )
    phone = _decrypt_required(secret_service, userbot.phone_number_encrypted, "phone_number")
    client = client_factory(_client_config(secret_service, userbot))
    try:
        result = await client.sign_in_code(
            phone_number=phone,
            code=normalized_code,
            phone_code_hash=phone_code_hash,
        )
    except UserbotPasswordRequired as exc:
        if exc.partial_session_string:
            userbot.session_encrypted = secret_service.encrypt(exc.partial_session_string)
        auth_session.status = "password_required"
        auth_session.updated_at = utcnow()
        userbot.auth_status = "password_required"
        userbot.runtime_status = _runtime_status_for_enabled(userbot.enabled)
        userbot.updated_at = utcnow()
        await session.flush()
        await create_audit_log(
            session,
            actor=actor,
            action="summary_userbot_password_required",
            entity_type="summary_userbot",
            entity_id=str(userbot.id),
            redacted_after={"auth_status": userbot.auth_status},
        )
        return _userbot_view(userbot)
    except UserbotClientError as exc:
        await _mark_auth_session_error(
            session,
            userbot,
            auth_session,
            error_type=exc.error_type,
            message=str(exc),
        )
        raise UserbotAuthFlowError(str(exc)) from exc

    await _complete_authorization(
        session,
        secret_service=secret_service,
        userbot=userbot,
        auth_session=auth_session,
        result=result,
        actor=actor,
    )
    return _userbot_view(userbot)


async def submit_summary_userbot_password(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    password: str,
    client_factory: UserbotClientFactory = create_telethon_userbot_client,
    userbot_id: int | None = None,
    actor: str = "system",
) -> SummaryUserbotView:
    normalized_password = _normalize_required_text(password, "password")
    userbot = await _resolve_userbot(session, userbot_id)
    auth_session = await _latest_auth_session(
        session,
        userbot,
        expected_status="password_required",
    )
    client = client_factory(_client_config(secret_service, userbot))
    try:
        result = await client.sign_in_password(normalized_password)
    except UserbotClientError as exc:
        await _mark_auth_session_error(
            session,
            userbot,
            auth_session,
            error_type=exc.error_type,
            message=str(exc),
        )
        raise UserbotAuthFlowError(str(exc)) from exc

    await _complete_authorization(
        session,
        secret_service=secret_service,
        userbot=userbot,
        auth_session=auth_session,
        result=result,
        actor=actor,
    )
    return _userbot_view(userbot)


async def load_enabled_userbot_runtime_config(
    session: AsyncSession,
    *,
    secret_service: SecretService,
) -> UserbotRuntimeConfig | None:
    userbot = await enabled_summary_userbot(session)
    if userbot is None or userbot.auth_status != "authorized":
        return None
    if userbot.api_id is None:
        raise UserbotConfigError("enabled summary userbot is missing api_id")
    return UserbotRuntimeConfig(
        userbot_id=userbot.id,
        api_id=userbot.api_id,
        api_hash=_decrypt_required(secret_service, userbot.api_hash_encrypted, "api_hash"),
        phone_number=_decrypt_required(secret_service, userbot.phone_number_encrypted, "phone_number"),
        session_string=_decrypt_required(secret_service, userbot.session_encrypted, "session"),
        proxy_url=_decrypt_optional(secret_service, userbot.proxy_url_encrypted),
        name=userbot.name,
    )


def summary_userbot_view(userbot: SummaryUserbot) -> SummaryUserbotView:
    return _userbot_view(userbot)


def _userbot_view(userbot: SummaryUserbot) -> SummaryUserbotView:
    return SummaryUserbotView(
        id=userbot.id,
        name=userbot.name,
        api_id=userbot.api_id,
        phone_number_redacted=_redact_encrypted_phone(userbot.phone_number_encrypted),
        enabled=userbot.enabled,
        auth_status=userbot.auth_status,
        runtime_status=userbot.runtime_status,
        telegram_user_id=userbot.telegram_user_id,
        telegram_username=userbot.telegram_username,
        telegram_display_name=userbot.telegram_display_name,
        last_authorized_at=userbot.last_authorized_at,
        last_started_at=userbot.last_started_at,
        last_stopped_at=userbot.last_stopped_at,
        last_error_type=userbot.last_error_type,
        last_error_message=userbot.last_error_message,
        created_at=userbot.created_at,
        updated_at=userbot.updated_at,
        secrets=SummaryUserbotSecretState(
            api_hash=SecretState(configured=bool(userbot.api_hash_encrypted), updated_at=None),
            phone_number=SecretState(configured=bool(userbot.phone_number_encrypted), updated_at=None),
            session=SecretState(configured=bool(userbot.session_encrypted), updated_at=None),
            proxy_url=SecretState(configured=bool(userbot.proxy_url_encrypted), updated_at=None),
        ),
    )


def _userbot_redacted_dict(userbot: SummaryUserbot) -> dict[str, Any]:
    return {
        "id": userbot.id,
        "name": userbot.name,
        "api_id": userbot.api_id,
        "api_hash": redact_configured_secret(userbot.api_hash_encrypted),
        "phone_number": _redact_encrypted_phone(userbot.phone_number_encrypted),
        "session": redact_configured_secret(userbot.session_encrypted),
        "proxy_url": redact_configured_secret(userbot.proxy_url_encrypted),
        "telegram_user_id": userbot.telegram_user_id,
        "telegram_username": userbot.telegram_username,
        "telegram_display_name": userbot.telegram_display_name,
        "enabled": userbot.enabled,
        "auth_status": userbot.auth_status,
        "runtime_status": userbot.runtime_status,
        "last_authorized_at": userbot.last_authorized_at.isoformat()
        if userbot.last_authorized_at is not None
        else None,
        "last_error_type": userbot.last_error_type,
        "last_error_message": userbot.last_error_message,
    }


async def _resolve_userbot(session: AsyncSession, userbot_id: int | None) -> SummaryUserbot:
    if userbot_id is not None:
        return await get_summary_userbot(session, userbot_id)
    active, item = await list_current_userbot(session)
    selected = active or item
    if selected is None:
        raise UserbotNotFoundError("summary userbot not found")
    return await get_summary_userbot(session, selected.id)


async def _latest_auth_session(
    session: AsyncSession,
    userbot: SummaryUserbot,
    *,
    expected_status: str,
) -> SummaryUserbotAuthSession:
    auth_session = await session.scalar(
        select(SummaryUserbotAuthSession)
        .where(SummaryUserbotAuthSession.userbot_id == userbot.id)
        .where(SummaryUserbotAuthSession.status == expected_status)
        .order_by(SummaryUserbotAuthSession.id.desc())
        .limit(1)
    )
    if auth_session is None:
        raise UserbotAuthFlowError("active authorization session was not found")
    if _as_aware_utc(auth_session.expires_at) <= utcnow():
        auth_session.status = "expired"
        auth_session.updated_at = utcnow()
        userbot.auth_status = "error"
        userbot.runtime_status = _runtime_status_for_enabled(userbot.enabled)
        userbot.last_error_type = "auth_session_expired"
        userbot.last_error_message = "authorization session has expired"
        userbot.updated_at = utcnow()
        await session.flush()
        raise UserbotAuthFlowError("authorization session has expired")
    return auth_session


async def _expire_active_auth_sessions(
    session: AsyncSession,
    userbot: SummaryUserbot,
) -> None:
    sessions = (
        await session.scalars(
            select(SummaryUserbotAuthSession)
            .where(SummaryUserbotAuthSession.userbot_id == userbot.id)
            .where(SummaryUserbotAuthSession.status.in_(_ACTIVE_AUTH_SESSION_STATUSES))
        )
    ).all()
    now = utcnow()
    for auth_session in sessions:
        auth_session.status = "expired"
        auth_session.updated_at = now
    if sessions:
        await session.flush()


async def _disable_userbot_summary_entities(session: AsyncSession, *, userbot_id: int, now: datetime) -> None:
    groups = (
        await session.scalars(
            select(SummaryEntity).where(
                SummaryEntity.userbot_id == userbot_id,
                SummaryEntity.enabled.is_(True),
            )
        )
    ).all()
    for group in groups:
        group.enabled = False
        group.collection_status = "disabled"
        group.updated_at = now
    if groups:
        await session.flush()


async def _complete_authorization(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    userbot: SummaryUserbot,
    auth_session: SummaryUserbotAuthSession,
    result: UserbotAuthResult,
    actor: str,
) -> None:
    now = utcnow()
    userbot.session_encrypted = secret_service.encrypt(result.session_string)
    userbot.telegram_user_id = result.identity.telegram_user_id
    userbot.telegram_username = result.identity.telegram_username
    userbot.telegram_display_name = result.identity.telegram_display_name
    userbot.auth_status = "authorized"
    userbot.runtime_status = _runtime_status_for_enabled(userbot.enabled)
    userbot.last_authorized_at = now
    userbot.last_error_type = None
    userbot.last_error_message = None
    userbot.updated_at = now
    auth_session.status = "completed"
    auth_session.updated_at = now
    auth_session.last_error_type = None
    auth_session.last_error_message = None
    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action="authorize_summary_userbot",
        entity_type="summary_userbot",
        entity_id=str(userbot.id),
        redacted_after={
            "auth_status": userbot.auth_status,
            "runtime_status": userbot.runtime_status,
            "telegram_user_id": userbot.telegram_user_id,
            "telegram_username": userbot.telegram_username,
            "telegram_display_name": userbot.telegram_display_name,
            "session": redact_configured_secret(userbot.session_encrypted),
        },
    )


async def _mark_userbot_auth_error(
    session: AsyncSession,
    userbot: SummaryUserbot,
    *,
    error_type: str,
    message: str,
) -> None:
    userbot.auth_status = "error"
    userbot.runtime_status = _runtime_status_for_enabled(userbot.enabled)
    userbot.last_error_type = error_type
    userbot.last_error_message = message
    userbot.updated_at = utcnow()
    await session.flush()


async def _mark_auth_session_error(
    session: AsyncSession,
    userbot: SummaryUserbot,
    auth_session: SummaryUserbotAuthSession,
    *,
    error_type: str,
    message: str,
) -> None:
    auth_session.status = "failed"
    auth_session.last_error_type = error_type
    auth_session.last_error_message = message
    auth_session.updated_at = utcnow()
    await _mark_userbot_auth_error(session, userbot, error_type=error_type, message=message)


def _client_config(secret_service: SecretService, userbot: SummaryUserbot) -> UserbotClientConfig:
    if userbot.api_id is None:
        raise UserbotConfigError("api_id is required")
    return UserbotClientConfig(
        api_id=userbot.api_id,
        api_hash=_decrypt_required(secret_service, userbot.api_hash_encrypted, "api_hash"),
        session_string=_decrypt_optional(secret_service, userbot.session_encrypted),
        proxy_url=_decrypt_optional(secret_service, userbot.proxy_url_encrypted),
    )


def _decrypt_required(secret_service: SecretService, value: str | None, field_name: str) -> str:
    if value is None:
        raise UserbotConfigError(f"{field_name} is required")
    try:
        return secret_service.decrypt(value)
    except SecretError as exc:
        raise UserbotConfigError(f"configured {field_name} could not be decrypted") from exc


def _decrypt_optional(secret_service: SecretService, value: str | None) -> str | None:
    if value is None:
        return None
    try:
        return secret_service.decrypt(value)
    except SecretError as exc:
        raise UserbotConfigError("configured userbot secret could not be decrypted") from exc


def _validate_api_id(api_id: int) -> None:
    if api_id <= 0:
        raise UserbotConfigError("api_id must be a positive integer")


def _validate_proxy_url(proxy_url: str) -> None:
    try:
        parse_userbot_proxy_url(proxy_url)
    except UserbotClientError as exc:
        raise UserbotConfigError(str(exc)) from exc


def _normalize_required_text(value: str, field_name: str) -> str:
    normalized = value.strip()
    if normalized == "":
        raise UserbotConfigError(f"{field_name} must not be empty")
    return normalized


def _normalize_optional_secret(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _runtime_status_for_enabled(enabled: bool) -> str:
    return "stopped" if enabled else "disabled"


def _as_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def _redact_encrypted_phone(encrypted_phone: str | None) -> str | None:
    if encrypted_phone is None:
        return None
    return "configured"
