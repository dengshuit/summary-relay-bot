from __future__ import annotations

import pytest

from summary_relay_bot.config import AppConfig, ConfigError


def valid_env() -> dict[str, str]:
    return {
        "BOT_TOKEN": "123456:secret-token",
        "OWNER_ID": "1001",
        "DATABASE_URL": "postgresql+asyncpg://user:db-secret@localhost/db",
        "LLM_API_KEY": "llm-secret",
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
