from __future__ import annotations

import pytest

from summary_relay_bot.config import AppConfig, BootstrapConfig, ConfigError


def valid_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "123456:secret-token",
        "OWNER_ID": "1001",
        "DATABASE_URL": "postgresql+asyncpg://user:db-secret@localhost/db",
        "LLM_API_KEY": "llm-secret",
    }


def valid_bootstrap_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql+asyncpg://user:db-secret@localhost/db",
        "SETTINGS_ENCRYPTION_KEY": "secret-encryption-key",
        "WEBUI_ADMIN_TOKEN": "secret-admin-token",
    }


def test_missing_bot_token_fails_before_clients_are_constructed() -> None:
    env = valid_env()
    del env["BOT_TOKEN"]

    with pytest.raises(ConfigError, match="BOT_TOKEN"):
        AppConfig.from_env(env)


@pytest.mark.parametrize("owner_id", ["", "abc", "0"])
def test_invalid_owner_id_is_rejected(owner_id: str) -> None:
    env = valid_env()
    env["OWNER_ID"] = owner_id

    with pytest.raises(ConfigError):
        AppConfig.from_env(env)


def test_config_repr_and_safe_dict_redact_secrets() -> None:
    config = AppConfig.from_env(valid_env())

    rendered = repr(config)
    safe = config.safe_dict()

    assert "secret-token" not in rendered
    assert "db-secret" not in rendered
    assert "llm-secret" not in rendered
    assert "1001" not in rendered
    assert safe["bot_token"] == "<redacted>"
    assert safe["owner_id"] == "<redacted>"
    assert "<redacted>" in str(safe["database_url"])
    assert safe["llm_api_key"] == "<redacted>"


def test_defaults_choose_polling_safe_anthropic_summary_settings() -> None:
    config = AppConfig.from_env(valid_env())

    assert config.allow_webhook_delete is False
    assert config.drop_pending_updates_on_webhook_delete is False
    assert config.raw_update_retention_days == 30
    assert config.llm_provider == "anthropic"
    assert config.llm_model == "claude-opus-4-8"
    assert config.summary_prompt_version == "v1"


def test_bootstrap_config_reads_only_startup_settings_and_redacts_secrets() -> None:
    config = BootstrapConfig.from_env(valid_bootstrap_env())

    rendered = repr(config)
    safe = config.safe_dict()

    assert config.webui_host == "127.0.0.1"
    assert config.webui_port == 8080
    assert "db-secret" not in rendered
    assert "secret-encryption-key" not in rendered
    assert "secret-admin-token" not in rendered
    assert "<redacted>" in str(safe["database_url"])
    assert safe["settings_encryption_key"] == "<redacted>"
    assert safe["webui_admin_token"] == "<redacted>"


def test_bootstrap_config_requires_bootstrap_secrets() -> None:
    env = valid_bootstrap_env()
    del env["SETTINGS_ENCRYPTION_KEY"]

    with pytest.raises(ConfigError, match="SETTINGS_ENCRYPTION_KEY"):
        BootstrapConfig.from_env(env)


def test_app_config_can_be_built_from_bootstrap_and_runtime_bot_without_business_env() -> None:
    bootstrap_config = BootstrapConfig.from_env(valid_bootstrap_env())

    config = AppConfig.from_bootstrap_runtime(
        bootstrap_config,
        bot_token="123456:runtime-secret-token",
        owner_id=2002,
        env={},
    )

    rendered = repr(config)
    assert config.bot_token == "123456:runtime-secret-token"
    assert config.owner_id == 2002
    assert config.database_url == bootstrap_config.database_url
    assert config.llm_api_key == ""
    assert "runtime-secret-token" not in rendered
    assert "2002" not in rendered


def test_app_config_from_bootstrap_runtime_keeps_non_bot_env_defaults_configurable() -> None:
    bootstrap_config = BootstrapConfig.from_env(valid_bootstrap_env())

    config = AppConfig.from_bootstrap_runtime(
        bootstrap_config,
        bot_token="123456:runtime-secret-token",
        owner_id=2002,
        env={
            "SUMMARY_DEFAULT_INTERVAL_MINUTES": "45",
            "SCHEDULER_TIMEZONE": "Asia/Shanghai",
            "LLM_MODEL": "claude-runtime",
        },
    )

    assert config.summary_default_interval_minutes == 45
    assert config.scheduler_timezone == "Asia/Shanghai"
    assert config.llm_model == "claude-runtime"
