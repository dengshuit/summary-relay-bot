from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from summary_relay_bot.db.models import (
    AuditLog,
    BotInstance,
    GroupChat,
    GroupSummarySettings,
    LLMProvider,
    SummaryProfile,
    utcnow,
)
from summary_relay_bot.services.secrets import SecretService, redact_configured_secret


class RuntimeConfigError(ValueError):
    pass


SUPPORTED_LLM_PROVIDER_TYPES = frozenset({"anthropic", "openai", "openai_compatible"})


@dataclass(frozen=True, slots=True)
class BotRuntimeConfig:
    bot_instance_id: int
    bot_token: str
    owner_id: int
    name: str
    needs_restart: bool


@dataclass(frozen=True, slots=True)
class LLMProviderRuntimeConfig:
    llm_provider_id: int
    provider_type: str
    api_key: str
    default_model: str
    timeout_seconds: int
    max_retries: int
    base_url: str | None = None


@dataclass(frozen=True, slots=True)
class SummaryProfileRuntimeConfig:
    summary_profile_id: int
    llm_provider: LLMProviderRuntimeConfig
    model: str
    prompt_version: str
    system_prompt: str | None
    temperature: float | None
    max_output_tokens: int | None


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


async def enabled_bot_instance(session: AsyncSession) -> BotInstance | None:
    return await session.scalar(select(BotInstance).where(BotInstance.enabled.is_(True)))


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
