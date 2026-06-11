from __future__ import annotations

import pytest

from summary_relay_bot.config import AppConfig, BootstrapConfig, ConfigError


def valid_bootstrap_env() -> dict[str, str]:
    return {
        "DATABASE_URL": "postgresql+asyncpg://user:db-secret@localhost/db",
        "SETTINGS_ENCRYPTION_KEY": "secret-encryption-key",
        "WEBUI_ADMIN_TOKEN": "secret-admin-token",
    }


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


def test_bootstrap_config_requires_bootstrap_secrets_only() -> None:
    env = valid_bootstrap_env()
    del env["SETTINGS_ENCRYPTION_KEY"]

    with pytest.raises(ConfigError, match="SETTINGS_ENCRYPTION_KEY"):
        BootstrapConfig.from_env(env)


def test_process_config_can_be_built_without_legacy_business_env() -> None:
    bootstrap_config = BootstrapConfig.from_env(valid_bootstrap_env())

    config = AppConfig.from_bootstrap_runtime(
        bootstrap_config,
        env={},
    )

    rendered = repr(config)
    safe = config.safe_dict()

    assert config.database_url == bootstrap_config.database_url
    assert config.allow_webhook_delete is False
    assert config.drop_pending_updates_on_webhook_delete is False
    assert config.raw_update_retention_days == 30
    assert config.scheduler_timezone == "UTC"
    assert config.scheduler_misfire_grace_seconds == 300
    assert config.scheduler_coalesce is True
    assert "db-secret" not in rendered
    assert "<redacted>" in str(safe["database_url"])


def test_process_config_keeps_process_env_options_configurable() -> None:
    bootstrap_config = BootstrapConfig.from_env(valid_bootstrap_env())

    config = AppConfig.from_bootstrap_runtime(
        bootstrap_config,
        env={
            "ALLOW_WEBHOOK_DELETE": "true",
            "DROP_PENDING_UPDATES_ON_WEBHOOK_DELETE": "true",
            "RAW_UPDATE_RETENTION_DAYS": "14",
            "SCHEDULER_TIMEZONE": "Asia/Shanghai",
            "SCHEDULER_MISFIRE_GRACE_SECONDS": "60",
            "SCHEDULER_COALESCE": "false",
        },
    )

    assert config.allow_webhook_delete is True
    assert config.drop_pending_updates_on_webhook_delete is True
    assert config.raw_update_retention_days == 14
    assert config.scheduler_timezone == "Asia/Shanghai"
    assert config.scheduler_misfire_grace_seconds == 60
    assert config.scheduler_coalesce is False


def test_process_config_rejects_invalid_process_env() -> None:
    bootstrap_config = BootstrapConfig.from_env(valid_bootstrap_env())

    with pytest.raises(ConfigError):
        AppConfig.from_bootstrap_runtime(
            bootstrap_config,
            env={"RAW_UPDATE_RETENTION_DAYS": "0"},
        )
