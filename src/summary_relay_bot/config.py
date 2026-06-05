from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


_SECRET_FIELD_NAMES = {"bot_token", "database_url", "llm_api_key"}
_SENSITIVE_NUMERIC_FIELD_NAMES = {"owner_id"}
_REQUIRED_ENV = ("BOT_TOKEN", "OWNER_ID", "DATABASE_URL", "LLM_API_KEY")


def _parse_bool(value: str | None, *, default: bool) -> bool:
    if value is None or value == "":
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError("boolean configuration value is invalid")


def _parse_int(value: str | None, name: str, *, minimum: int | None = None) -> int:
    if value is None or value.strip() == "":
        raise ConfigError(f"{name} is required")
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc
    if minimum is not None and parsed < minimum:
        raise ConfigError(f"{name} must be >= {minimum}")
    return parsed


def _require(env: Mapping[str, str], name: str) -> str:
    value = env.get(name)
    if value is None or value.strip() == "":
        raise ConfigError(f"{name} is required")
    return value.strip()


def redact_secret(value: str | None) -> str | None:
    if value is None:
        return None
    if value == "":
        return ""
    return "<redacted>"


def redact_database_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.password is None:
        return value
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    userinfo = f"{username}:<redacted>@" if username else "<redacted>@"
    netloc = f"{userinfo}{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@dataclass(frozen=True, slots=True)
class AppConfig:
    bot_token: str
    owner_id: int
    database_url: str
    allow_webhook_delete: bool = False
    drop_pending_updates_on_webhook_delete: bool = False
    raw_update_retention_days: int = 30
    summary_default_interval_minutes: int = 300
    scheduler_timezone: str = "UTC"
    scheduler_misfire_grace_seconds: int = 300
    scheduler_coalesce: bool = True
    llm_provider: str = "anthropic"
    llm_api_key: str = ""
    llm_model: str = "claude-opus-4-8"
    llm_timeout_seconds: int = 30
    summary_prompt_version: str = "v1"

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "AppConfig":
        missing = [name for name in _REQUIRED_ENV if not env.get(name)]
        if missing:
            raise ConfigError(f"missing required configuration: {', '.join(missing)}")

        bot_token = _require(env, "BOT_TOKEN")
        database_url = _require(env, "DATABASE_URL")
        llm_api_key = _require(env, "LLM_API_KEY")

        return cls(
            bot_token=bot_token,
            owner_id=_parse_int(env.get("OWNER_ID"), "OWNER_ID", minimum=1),
            database_url=database_url,
            allow_webhook_delete=_parse_bool(env.get("ALLOW_WEBHOOK_DELETE"), default=False),
            drop_pending_updates_on_webhook_delete=_parse_bool(
                env.get("DROP_PENDING_UPDATES_ON_WEBHOOK_DELETE"), default=False
            ),
            raw_update_retention_days=_parse_int(
                env.get("RAW_UPDATE_RETENTION_DAYS", "30"),
                "RAW_UPDATE_RETENTION_DAYS",
                minimum=1,
            ),
            summary_default_interval_minutes=_parse_int(
                env.get("SUMMARY_DEFAULT_INTERVAL_MINUTES", "300"),
                "SUMMARY_DEFAULT_INTERVAL_MINUTES",
                minimum=1,
            ),
            scheduler_timezone=env.get("SCHEDULER_TIMEZONE", "UTC").strip() or "UTC",
            scheduler_misfire_grace_seconds=_parse_int(
                env.get("SCHEDULER_MISFIRE_GRACE_SECONDS", "300"),
                "SCHEDULER_MISFIRE_GRACE_SECONDS",
                minimum=0,
            ),
            scheduler_coalesce=_parse_bool(env.get("SCHEDULER_COALESCE"), default=True),
            llm_provider=env.get("LLM_PROVIDER", "anthropic").strip() or "anthropic",
            llm_api_key=llm_api_key,
            llm_model=env.get("LLM_MODEL", "claude-opus-4-8").strip() or "claude-opus-4-8",
            llm_timeout_seconds=_parse_int(
                env.get("LLM_TIMEOUT_SECONDS", "30"),
                "LLM_TIMEOUT_SECONDS",
                minimum=1,
            ),
            summary_prompt_version=env.get("SUMMARY_PROMPT_VERSION", "v1").strip() or "v1",
        )

    def safe_dict(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "database_url":
                result[field.name] = redact_database_url(str(value))
            elif field.name in _SECRET_FIELD_NAMES:
                result[field.name] = redact_secret(str(value))
            elif field.name in _SENSITIVE_NUMERIC_FIELD_NAMES:
                result[field.name] = "<redacted>"
            else:
                result[field.name] = value
        return result

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"AppConfig({args})"
