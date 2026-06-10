from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from aiogram.exceptions import TelegramAPIError, TelegramUnauthorizedError
from aiogram.utils.token import TokenValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from summary_relay_bot.config import redact_secret
from summary_relay_bot.db.models import (
    AuditLog,
    BotInstance,
    GroupChat,
    GroupSummarySettings,
    LLMProvider,
    SummaryProfile,
    utcnow,
)
from summary_relay_bot.services.secrets import SecretError, SecretService, redact_configured_secret
from summary_relay_bot.telegram.bot import create_bot


class RuntimeConfigError(ValueError):
    pass


class BotInstanceNotFoundError(RuntimeConfigError):
    pass


SUPPORTED_LLM_PROVIDER_TYPES = frozenset({"anthropic", "openai", "openai_compatible"})
_UNSET = object()


def redact_owner_id(owner_id: int | None) -> str | None:
    if owner_id is None:
        return None
    rendered = str(owner_id)
    if len(rendered) <= 4:
        return "*" * len(rendered)
    return f"{rendered[:2]}***{rendered[-2:]}"


@dataclass(frozen=True, slots=True)
class BotRuntimeConfig:
    bot_instance_id: int
    bot_token: str
    owner_id: int
    name: str
    needs_restart: bool

    def safe_dict(self) -> dict[str, object]:
        return {
            "bot_instance_id": self.bot_instance_id,
            "bot_token": redact_secret(self.bot_token),
            "owner_id": "<redacted>",
            "name": self.name,
            "needs_restart": self.needs_restart,
        }

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"BotRuntimeConfig({args})"


@dataclass(frozen=True, slots=True)
class SecretState:
    configured: bool
    updated_at: datetime | None


@dataclass(frozen=True, slots=True)
class BotInstanceView:
    id: int
    name: str
    owner_id_redacted: str
    telegram_bot_id: int | None
    telegram_username: str | None
    enabled: bool
    status: str
    needs_restart: bool
    last_validated_at: datetime | None
    secret: SecretState


@dataclass(frozen=True, slots=True)
class BotIdentity:
    telegram_bot_id: int
    telegram_username: str | None


@dataclass(frozen=True, slots=True)
class BotValidationResult:
    status: str
    last_validated_at: datetime
    telegram_bot_id: int | None
    telegram_username: str | None
    error_type: str | None = None
    error_message: str | None = None


@dataclass(frozen=True, slots=True)
class _BotTokenConfig:
    bot_token: str


@dataclass(frozen=True, slots=True)
class LLMProviderRuntimeConfig:
    llm_provider_id: int
    provider_type: str
    api_key: str
    default_model: str
    timeout_seconds: int
    max_retries: int
    base_url: str | None = None

    def safe_dict(self) -> dict[str, object]:
        return {
            "llm_provider_id": self.llm_provider_id,
            "provider_type": self.provider_type,
            "api_key": redact_secret(self.api_key),
            "default_model": self.default_model,
            "timeout_seconds": self.timeout_seconds,
            "max_retries": self.max_retries,
            "base_url": self.base_url,
        }

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"LLMProviderRuntimeConfig({args})"


@dataclass(frozen=True, slots=True)
class SummaryProfileRuntimeConfig:
    summary_profile_id: int
    llm_provider: LLMProviderRuntimeConfig
    model: str
    prompt_version: str
    system_prompt: str | None
    temperature: float | None
    max_output_tokens: int | None

    def safe_dict(self) -> dict[str, object]:
        return {
            "summary_profile_id": self.summary_profile_id,
            "llm_provider": self.llm_provider.safe_dict(),
            "model": self.model,
            "prompt_version": self.prompt_version,
            "system_prompt": self.system_prompt,
            "temperature": self.temperature,
            "max_output_tokens": self.max_output_tokens,
        }

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"SummaryProfileRuntimeConfig({args})"


async def create_audit_log(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: str | None = None,
    redacted_before: dict[str, Any] | None = None,
    redacted_after: dict[str, Any] | None = None,
) -> AuditLog:
    audit_log = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        redacted_before=redacted_before,
        redacted_after=redacted_after,
    )
    session.add(audit_log)
    await session.flush()
    return audit_log


async def create_bot_instance(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    name: str,
    bot_token: str,
    owner_id: int,
    enabled: bool = False,
    actor: str = "system",
) -> BotInstance:
    if owner_id <= 0:
        raise RuntimeConfigError("owner_id must be a positive integer")
    if enabled and await enabled_bot_instance(session) is not None:
        raise RuntimeConfigError("only one bot instance can be enabled")

    bot_instance = BotInstance(
        name=name,
        bot_token_encrypted=secret_service.encrypt(bot_token),
        owner_id=owner_id,
        enabled=enabled,
    )
    session.add(bot_instance)
    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action="create_bot_instance",
        entity_type="bot_instance",
        entity_id=str(bot_instance.id),
        redacted_after={
            "name": bot_instance.name,
            "bot_token": redact_configured_secret(bot_instance.bot_token_encrypted),
            "owner_id": "<redacted>",
            "enabled": bot_instance.enabled,
        },
    )
    return bot_instance


def _bot_instance_redacted_dict(bot_instance: BotInstance) -> dict[str, Any]:
    return {
        "id": bot_instance.id,
        "name": bot_instance.name,
        "owner_id": redact_owner_id(bot_instance.owner_id),
        "telegram_bot_id": bot_instance.telegram_bot_id,
        "telegram_username": bot_instance.telegram_username,
        "enabled": bot_instance.enabled,
        "status": bot_instance.status,
        "needs_restart": bot_instance.needs_restart,
        "last_validated_at": bot_instance.last_validated_at.isoformat()
        if bot_instance.last_validated_at is not None
        else None,
        "bot_token": redact_configured_secret(bot_instance.bot_token_encrypted),
    }


def _bot_instance_view(bot_instance: BotInstance) -> BotInstanceView:
    return BotInstanceView(
        id=bot_instance.id,
        name=bot_instance.name,
        owner_id_redacted=redact_owner_id(bot_instance.owner_id) or "",
        telegram_bot_id=bot_instance.telegram_bot_id,
        telegram_username=bot_instance.telegram_username,
        enabled=bot_instance.enabled,
        status=bot_instance.status,
        needs_restart=bot_instance.needs_restart,
        last_validated_at=bot_instance.last_validated_at,
        secret=SecretState(
            configured=bool(bot_instance.bot_token_encrypted),
            updated_at=None,
        ),
    )


async def enabled_bot_instance(session: AsyncSession) -> BotInstance | None:
    return await session.scalar(select(BotInstance).where(BotInstance.enabled.is_(True)))


async def list_bot_instances(session: AsyncSession) -> tuple[BotInstanceView | None, list[BotInstanceView]]:
    bot_instances = (
        await session.scalars(select(BotInstance).order_by(BotInstance.id))
    ).all()
    active = next((bot_instance for bot_instance in bot_instances if bot_instance.enabled), None)
    active_id = active.id if active is not None else None
    return (
        _bot_instance_view(active) if active is not None else None,
        [
            _bot_instance_view(bot_instance)
            for bot_instance in bot_instances
            if bot_instance.id != active_id
        ],
    )


async def get_bot_instance(session: AsyncSession, bot_instance_id: int) -> BotInstance:
    bot_instance = await session.get(BotInstance, bot_instance_id)
    if bot_instance is None:
        raise BotInstanceNotFoundError("bot instance not found")
    return bot_instance


async def load_bot_runtime_config(
    session: AsyncSession,
    *,
    secret_service: SecretService,
) -> BotRuntimeConfig | None:
    bot_instance = await enabled_bot_instance(session)
    if bot_instance is None:
        return None
    return BotRuntimeConfig(
        bot_instance_id=bot_instance.id,
        bot_token=secret_service.decrypt(bot_instance.bot_token_encrypted),
        owner_id=bot_instance.owner_id,
        name=bot_instance.name,
        needs_restart=bot_instance.needs_restart,
    )


async def fetch_bot_identity(bot_token: str) -> BotIdentity:
    bot = create_bot(_BotTokenConfig(bot_token=bot_token))
    try:
        user = await bot.get_me()
        return BotIdentity(
            telegram_bot_id=user.id,
            telegram_username=user.username,
        )
    finally:
        await bot.session.close()


async def validate_bot_instance(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    bot_instance_id: int,
    bot_token: str | None | object = _UNSET,
) -> BotValidationResult:
    bot_instance = await get_bot_instance(session, bot_instance_id)
    normalized_token: str | None = None
    if bot_token is not _UNSET and bot_token is not None:
        normalized_token = bot_token.strip()

    should_persist_result = normalized_token is None or normalized_token == ""
    now = utcnow()
    try:
        token_to_validate = (
            secret_service.decrypt(bot_instance.bot_token_encrypted)
            if should_persist_result
            else normalized_token
        )
        identity = await fetch_bot_identity(token_to_validate)
    except SecretError:
        result = BotValidationResult(
            status="error",
            last_validated_at=now,
            telegram_bot_id=None,
            telegram_username=None,
            error_type="secret_error",
            error_message="configured bot token could not be decrypted",
        )
    except (TokenValidationError, TelegramUnauthorizedError):
        result = BotValidationResult(
            status="invalid",
            last_validated_at=now,
            telegram_bot_id=None,
            telegram_username=None,
            error_type="invalid_token",
            error_message="bot token is invalid",
        )
    except TelegramAPIError:
        result = BotValidationResult(
            status="error",
            last_validated_at=now,
            telegram_bot_id=None,
            telegram_username=None,
            error_type="telegram_error",
            error_message="Telegram validation failed",
        )
    else:
        result = BotValidationResult(
            status="valid",
            last_validated_at=now,
            telegram_bot_id=identity.telegram_bot_id,
            telegram_username=identity.telegram_username,
        )

    if should_persist_result:
        bot_instance.status = result.status
        bot_instance.last_validated_at = result.last_validated_at
        bot_instance.telegram_bot_id = result.telegram_bot_id
        bot_instance.telegram_username = result.telegram_username
        bot_instance.updated_at = now
        await session.flush()

    return result


async def update_bot_instance(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    bot_instance_id: int,
    name: str | None | object = _UNSET,
    owner_id: int | None | object = _UNSET,
    enabled: bool | None | object = _UNSET,
    bot_token: str | None | object = _UNSET,
    actor: str = "system",
) -> BotInstanceView:
    bot_instance = await get_bot_instance(session, bot_instance_id)
    redacted_before = _bot_instance_redacted_dict(bot_instance)

    changed_general = False
    replaced_token = False
    changed_enabled = False
    disabled_bot_ids: list[int] = []

    if name is not _UNSET and name is not None:
        normalized_name = name.strip()
        if normalized_name == "":
            raise RuntimeConfigError("name must not be empty")
        if normalized_name != bot_instance.name:
            bot_instance.name = normalized_name
            changed_general = True

    if owner_id is not _UNSET and owner_id is not None:
        if owner_id <= 0:
            raise RuntimeConfigError("owner_id must be a positive integer")
        if owner_id != bot_instance.owner_id:
            bot_instance.owner_id = owner_id
            bot_instance.needs_restart = True
            changed_general = True

    if bot_token is not _UNSET and bot_token is not None:
        normalized_token = bot_token.strip()
        if normalized_token != "":
            bot_instance.bot_token_encrypted = secret_service.encrypt(normalized_token)
            bot_instance.status = "unvalidated"
            bot_instance.last_validated_at = None
            bot_instance.telegram_bot_id = None
            bot_instance.telegram_username = None
            bot_instance.needs_restart = True
            replaced_token = True

    if enabled is not _UNSET and enabled is not None:
        if enabled:
            other_enabled = (
                await session.scalars(
                    select(BotInstance)
                    .where(BotInstance.enabled.is_(True))
                    .where(BotInstance.id != bot_instance.id)
                    .order_by(BotInstance.id)
                )
            ).all()
            now = utcnow()
            for other_bot in other_enabled:
                other_bot.enabled = False
                other_bot.needs_restart = True
                other_bot.updated_at = now
                disabled_bot_ids.append(other_bot.id)
            if other_enabled:
                await session.flush()
            if not bot_instance.enabled:
                bot_instance.enabled = True
                bot_instance.needs_restart = True
                changed_enabled = True
            elif disabled_bot_ids:
                changed_enabled = True
        elif bot_instance.enabled:
            bot_instance.enabled = False
            bot_instance.needs_restart = True
            changed_enabled = True

    if changed_general or replaced_token or changed_enabled:
        bot_instance.updated_at = utcnow()
        await session.flush()
        redacted_after = _bot_instance_redacted_dict(bot_instance)
        if replaced_token:
            await create_audit_log(
                session,
                actor=actor,
                action="replace_bot_token",
                entity_type="bot_instance",
                entity_id=str(bot_instance.id),
                redacted_before={
                    "bot_token": redacted_before["bot_token"],
                    "needs_restart": redacted_before["needs_restart"],
                },
                redacted_after={
                    "bot_token": redacted_after["bot_token"],
                    "needs_restart": redacted_after["needs_restart"],
                },
            )
        if changed_general:
            await create_audit_log(
                session,
                actor=actor,
                action="update_bot_instance",
                entity_type="bot_instance",
                entity_id=str(bot_instance.id),
                redacted_before=redacted_before,
                redacted_after=redacted_after,
            )
        if changed_enabled:
            enabled_after = {
                "enabled": redacted_after["enabled"],
                "needs_restart": redacted_after["needs_restart"],
            }
            if disabled_bot_ids:
                enabled_after["disabled_bot_ids"] = disabled_bot_ids
            await create_audit_log(
                session,
                actor=actor,
                action="enable_bot_instance" if bot_instance.enabled else "update_bot_instance",
                entity_type="bot_instance",
                entity_id=str(bot_instance.id),
                redacted_before={
                    "enabled": redacted_before["enabled"],
                    "needs_restart": redacted_before["needs_restart"],
                },
                redacted_after=enabled_after,
            )

    return _bot_instance_view(bot_instance)


async def create_llm_provider(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    name: str,
    provider_type: str,
    api_key: str,
    default_model: str,
    base_url: str | None = None,
    timeout_seconds: int = 30,
    max_retries: int = 2,
    enabled: bool = True,
    actor: str = "system",
) -> LLMProvider:
    if provider_type not in SUPPORTED_LLM_PROVIDER_TYPES:
        raise RuntimeConfigError("provider_type is not supported")
    if timeout_seconds <= 0:
        raise RuntimeConfigError("timeout_seconds must be positive")
    if max_retries < 0:
        raise RuntimeConfigError("max_retries must be non-negative")

    provider = LLMProvider(
        name=name,
        provider_type=provider_type,
        base_url=base_url,
        api_key_encrypted=secret_service.encrypt(api_key),
        default_model=default_model,
        timeout_seconds=timeout_seconds,
        max_retries=max_retries,
        enabled=enabled,
    )
    session.add(provider)
    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action="create_llm_provider",
        entity_type="llm_provider",
        entity_id=str(provider.id),
        redacted_after={
            "name": provider.name,
            "provider_type": provider.provider_type,
            "api_key": redact_configured_secret(provider.api_key_encrypted),
            "default_model": provider.default_model,
            "enabled": provider.enabled,
        },
    )
    return provider


async def create_summary_profile(
    session: AsyncSession,
    *,
    name: str,
    llm_provider: LLMProvider,
    model: str | None = None,
    prompt_version: str = "v1",
    system_prompt: str | None = None,
    temperature: float | None = None,
    max_output_tokens: int | None = None,
    enabled: bool = True,
    is_default: bool = False,
    actor: str = "system",
) -> SummaryProfile:
    if temperature is not None and not 0 <= temperature <= 2:
        raise RuntimeConfigError("temperature must be between 0 and 2")
    if max_output_tokens is not None and max_output_tokens <= 0:
        raise RuntimeConfigError("max_output_tokens must be positive")
    if is_default:
        existing_default = await default_summary_profile(session)
        if existing_default is not None:
            raise RuntimeConfigError("only one summary profile can be default")

    profile = SummaryProfile(
        name=name,
        llm_provider=llm_provider,
        model=model,
        prompt_version=prompt_version,
        system_prompt=system_prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        enabled=enabled,
        is_default=is_default,
    )
    session.add(profile)
    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action="create_summary_profile",
        entity_type="summary_profile",
        entity_id=str(profile.id),
        redacted_after={
            "name": profile.name,
            "llm_provider_id": profile.llm_provider_id,
            "model": profile.model,
            "prompt_version": profile.prompt_version,
            "enabled": profile.enabled,
            "is_default": profile.is_default,
        },
    )
    return profile


async def default_summary_profile(session: AsyncSession) -> SummaryProfile | None:
    return await session.scalar(select(SummaryProfile).where(SummaryProfile.is_default.is_(True)))


async def set_group_summary_settings(
    session: AsyncSession,
    *,
    group: GroupChat,
    interval_minutes: int,
    enabled: bool,
    summary_profile: SummaryProfile | None = None,
    timezone: str = "UTC",
    actor: str = "system",
) -> GroupSummarySettings:
    if interval_minutes <= 0:
        raise RuntimeConfigError("interval_minutes must be positive")

    settings = await session.scalar(
        select(GroupSummarySettings).where(GroupSummarySettings.group_id == group.id)
    )
    before = None
    if settings is None:
        settings = GroupSummarySettings(
            group=group,
            interval_minutes=interval_minutes,
            enabled=enabled,
            summary_profile=summary_profile,
            timezone=timezone,
        )
        session.add(settings)
        action = "create_group_summary_settings"
    else:
        before = {
            "enabled": settings.enabled,
            "interval_minutes": settings.interval_minutes,
            "summary_profile_id": settings.summary_profile_id,
            "timezone": settings.timezone,
        }
        settings.interval_minutes = interval_minutes
        settings.enabled = enabled
        settings.summary_profile = summary_profile
        settings.timezone = timezone
        settings.updated_at = utcnow()
        action = "update_group_summary_settings"

    await session.flush()
    await create_audit_log(
        session,
        actor=actor,
        action=action,
        entity_type="group_summary_settings",
        entity_id=str(settings.id),
        redacted_before=before,
        redacted_after={
            "group_id": settings.group_id,
            "enabled": settings.enabled,
            "interval_minutes": settings.interval_minutes,
            "summary_profile_id": settings.summary_profile_id,
            "timezone": settings.timezone,
        },
    )
    return settings


async def load_summary_profile_runtime_config(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    group: GroupChat,
) -> SummaryProfileRuntimeConfig:
    settings = await session.scalar(
        select(GroupSummarySettings)
        .options(
            selectinload(GroupSummarySettings.summary_profile).selectinload(SummaryProfile.llm_provider),
        )
        .where(GroupSummarySettings.group_id == group.id)
    )
    profile = settings.summary_profile if settings and settings.summary_profile else None
    if profile is None:
        profile = await session.scalar(
            select(SummaryProfile)
            .options(selectinload(SummaryProfile.llm_provider))
            .where(SummaryProfile.is_default.is_(True))
        )
    if profile is None:
        raise RuntimeConfigError("no summary profile is configured")
    if not profile.enabled:
        raise RuntimeConfigError("summary profile is disabled")
    provider = profile.llm_provider
    if not provider.enabled:
        raise RuntimeConfigError("llm provider is disabled")

    provider_config = LLMProviderRuntimeConfig(
        llm_provider_id=provider.id,
        provider_type=provider.provider_type,
        api_key=secret_service.decrypt(provider.api_key_encrypted),
        default_model=provider.default_model,
        timeout_seconds=provider.timeout_seconds,
        max_retries=provider.max_retries,
        base_url=provider.base_url,
    )
    return SummaryProfileRuntimeConfig(
        summary_profile_id=profile.id,
        llm_provider=provider_config,
        model=profile.model or provider.default_model,
        prompt_version=profile.prompt_version,
        system_prompt=profile.system_prompt,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
    )
