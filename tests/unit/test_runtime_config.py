from __future__ import annotations

from sqlalchemy import select

from summary_relay_bot.db.models import AuditLog, BotInstance
from summary_relay_bot.db.repositories import upsert_group
from summary_relay_bot.services.runtime_config import (
    BotRuntimeConfig,
    LLMProviderRuntimeConfig,
    RuntimeConfigError,
    create_bot_instance,
    create_llm_provider,
    create_summary_profile,
    load_bot_runtime_config,
    load_summary_profile_runtime_config,
    set_group_summary_settings,
)
from summary_relay_bot.services.secrets import SecretService


def secret_service() -> SecretService:
    return SecretService(SecretService.generate_key())


async def test_create_bot_instance_encrypts_token_and_writes_redacted_audit_log(db_session) -> None:
    service = secret_service()

    bot = await create_bot_instance(
        db_session,
        secret_service=service,
        name="Main bot",
        bot_token="123:bot-secret",
        owner_id=1001,
        enabled=True,
        actor="admin",
    )

    [audit_log] = (await db_session.scalars(select(AuditLog))).all()
    assert bot.bot_token_encrypted != "123:bot-secret"
    assert "bot-secret" not in bot.bot_token_encrypted
    assert audit_log.actor == "admin"
    assert audit_log.redacted_after is not None
    assert audit_log.redacted_after["bot_token"] == "configured"
    assert "bot-secret" not in str(audit_log.redacted_after)


async def test_load_bot_runtime_config_decrypts_enabled_bot(db_session) -> None:
    service = secret_service()
    bot = await create_bot_instance(
        db_session,
        secret_service=service,
        name="Main bot",
        bot_token="123:bot-secret",
        owner_id=1001,
        enabled=True,
    )

    runtime = await load_bot_runtime_config(db_session, secret_service=service)

    assert runtime is not None
    assert runtime.bot_instance_id == bot.id
    assert runtime.bot_token == "123:bot-secret"
    assert runtime.owner_id == 1001
    assert "bot-secret" not in repr(runtime)
    assert "1001" not in repr(runtime)


def test_runtime_config_repr_redacts_decrypted_secrets() -> None:
    bot_runtime = BotRuntimeConfig(
        bot_instance_id=1,
        bot_token="123:bot-secret",
        owner_id=1001,
        name="Main bot",
        needs_restart=False,
    )
    llm_runtime = LLMProviderRuntimeConfig(
        llm_provider_id=2,
        provider_type="anthropic",
        api_key="llm-secret",
        default_model="claude-default",
        timeout_seconds=30,
        max_retries=2,
    )

    assert "bot-secret" not in repr(bot_runtime)
    assert "1001" not in repr(bot_runtime)
    assert "llm-secret" not in repr(llm_runtime)


async def test_only_one_enabled_bot_instance_is_allowed_by_service(db_session) -> None:
    service = secret_service()
    await create_bot_instance(
        db_session,
        secret_service=service,
        name="Main bot",
        bot_token="123:first",
        owner_id=1001,
        enabled=True,
    )

    try:
        await create_bot_instance(
            db_session,
            secret_service=service,
            name="Second bot",
            bot_token="123:second",
            owner_id=1002,
            enabled=True,
        )
    except RuntimeConfigError as exc:
        assert "only one bot instance" in str(exc)
    else:
        raise AssertionError("second enabled bot instance was accepted")

    rows = (await db_session.scalars(select(BotInstance))).all()
    assert len(rows) == 1


async def test_summary_profile_runtime_config_uses_group_profile_and_decrypts_provider_key(db_session) -> None:
    service = secret_service()
    provider = await create_llm_provider(
        db_session,
        secret_service=service,
        name="Anthropic",
        provider_type="anthropic",
        api_key="llm-secret",
        default_model="claude-default",
        timeout_seconds=45,
        max_retries=3,
    )
    default_profile = await create_summary_profile(
        db_session,
        name="Default",
        llm_provider=provider,
        model="claude-default-profile",
        is_default=True,
    )
    group_profile = await create_summary_profile(
        db_session,
        name="Group profile",
        llm_provider=provider,
        model="claude-group",
        prompt_version="v2",
    )
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")
    await set_group_summary_settings(
        db_session,
        group=group,
        enabled=True,
        interval_minutes=30,
        summary_profile=group_profile,
        actor="admin",
    )

    runtime = await load_summary_profile_runtime_config(db_session, secret_service=service, group=group)

    assert default_profile.is_default is True
    assert runtime.summary_profile_id == group_profile.id
    assert runtime.llm_provider.llm_provider_id == provider.id
    assert runtime.llm_provider.api_key == "llm-secret"
    assert runtime.model == "claude-group"
    assert runtime.prompt_version == "v2"


async def test_summary_profile_runtime_config_falls_back_to_default_profile(db_session) -> None:
    service = secret_service()
    provider = await create_llm_provider(
        db_session,
        secret_service=service,
        name="Anthropic",
        provider_type="anthropic",
        api_key="llm-secret",
        default_model="claude-default",
    )
    default_profile = await create_summary_profile(
        db_session,
        name="Default",
        llm_provider=provider,
        model=None,
        is_default=True,
    )
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")

    runtime = await load_summary_profile_runtime_config(db_session, secret_service=service, group=group)

    assert runtime.summary_profile_id == default_profile.id
    assert runtime.model == "claude-default"


async def test_summary_profile_runtime_config_rejects_missing_profile(db_session) -> None:
    service = secret_service()
    group = await upsert_group(db_session, chat_id=-100, chat_type="group", title="Group")

    try:
        await load_summary_profile_runtime_config(db_session, secret_service=service, group=group)
    except RuntimeConfigError as exc:
        assert "no summary profile" in str(exc)
    else:
        raise AssertionError("missing summary profile was accepted")


async def test_create_llm_provider_rejects_unsupported_provider_type(db_session) -> None:
    service = secret_service()

    try:
        await create_llm_provider(
            db_session,
            secret_service=service,
            name="Unknown",
            provider_type="unknown",
            api_key="llm-secret",
            default_model="model",
        )
    except RuntimeConfigError as exc:
        assert "provider_type" in str(exc)
    else:
        raise AssertionError("unsupported provider type was accepted")


async def test_create_summary_profile_validates_model_parameters(db_session) -> None:
    service = secret_service()
    provider = await create_llm_provider(
        db_session,
        secret_service=service,
        name="Anthropic",
        provider_type="anthropic",
        api_key="llm-secret",
        default_model="claude-default",
    )

    try:
        await create_summary_profile(
            db_session,
            name="Invalid",
            llm_provider=provider,
            temperature=3,
        )
    except RuntimeConfigError as exc:
        assert "temperature" in str(exc)
    else:
        raise AssertionError("invalid temperature was accepted")
