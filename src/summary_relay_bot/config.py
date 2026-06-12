from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Mapping
from urllib.parse import urlsplit, urlunsplit


class ConfigError(ValueError):
    """Raised when required configuration is missing or invalid."""


_SECRET_FIELD_NAMES = {
    "database_url",
    "settings_encryption_key",
    "telegram_api_proxy",
    "webui_admin_token",
}
_REQUIRED_BOOTSTRAP_ENV = ("DATABASE_URL", "SETTINGS_ENCRYPTION_KEY", "WEBUI_ADMIN_TOKEN")


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


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


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


def _app_runtime_options(env: Mapping[str, str]) -> dict[str, object]:
    return {
        "allow_webhook_delete": _parse_bool(env.get("ALLOW_WEBHOOK_DELETE"), default=False),
        "drop_pending_updates_on_webhook_delete": _parse_bool(
            env.get("DROP_PENDING_UPDATES_ON_WEBHOOK_DELETE"), default=False
        ),
        "raw_update_retention_days": _parse_int(
            env.get("RAW_UPDATE_RETENTION_DAYS", "30"),
            "RAW_UPDATE_RETENTION_DAYS",
            minimum=1,
        ),
        "scheduler_timezone": env.get("SCHEDULER_TIMEZONE", "UTC").strip() or "UTC",
        "scheduler_misfire_grace_seconds": _parse_int(
            env.get("SCHEDULER_MISFIRE_GRACE_SECONDS", "300"),
            "SCHEDULER_MISFIRE_GRACE_SECONDS",
            minimum=0,
        ),
        "scheduler_coalesce": _parse_bool(env.get("SCHEDULER_COALESCE"), default=True),
        "telegram_api_proxy": _optional_text(env.get("TELEGRAM_API_PROXY")),
    }


@dataclass(frozen=True, slots=True)
class BootstrapConfig:
    database_url: str
    settings_encryption_key: str
    webui_admin_token: str
    webui_host: str = "127.0.0.1"
    webui_port: int = 8080

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> "BootstrapConfig":
        missing = [name for name in _REQUIRED_BOOTSTRAP_ENV if not env.get(name)]
        if missing:
            raise ConfigError(f"missing required bootstrap configuration: {', '.join(missing)}")

        return cls(
            database_url=_require(env, "DATABASE_URL"),
            settings_encryption_key=_require(env, "SETTINGS_ENCRYPTION_KEY"),
            webui_admin_token=_require(env, "WEBUI_ADMIN_TOKEN"),
            webui_host=env.get("WEBUI_HOST", "127.0.0.1").strip() or "127.0.0.1",
            webui_port=_parse_int(env.get("WEBUI_PORT", "8080"), "WEBUI_PORT", minimum=1),
        )

    def safe_dict(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "database_url":
                result[field.name] = redact_database_url(str(value))
            elif field.name in _SECRET_FIELD_NAMES:
                result[field.name] = redact_secret(str(value))
            else:
                result[field.name] = value
        return result

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"BootstrapConfig({args})"


@dataclass(frozen=True, slots=True)
class AppConfig:
    database_url: str
    allow_webhook_delete: bool = False
    drop_pending_updates_on_webhook_delete: bool = False
    raw_update_retention_days: int = 30
    scheduler_timezone: str = "UTC"
    scheduler_misfire_grace_seconds: int = 300
    scheduler_coalesce: bool = True
    telegram_api_proxy: str | None = None

    @classmethod
    def from_bootstrap_runtime(
        cls,
        bootstrap_config: BootstrapConfig,
        *,
        env: Mapping[str, str],
    ) -> "AppConfig":
        return cls(
            database_url=bootstrap_config.database_url,
            **_app_runtime_options(env),
        )

    def safe_dict(self) -> dict[str, object]:
        result: dict[str, object] = {}
        for field in fields(self):
            value = getattr(self, field.name)
            if field.name == "database_url":
                result[field.name] = redact_database_url(str(value))
            elif field.name in _SECRET_FIELD_NAMES:
                result[field.name] = redact_secret(str(value))
            else:
                result[field.name] = value
        return result

    def __repr__(self) -> str:
        args = ", ".join(f"{key}={value!r}" for key, value in self.safe_dict().items())
        return f"AppConfig({args})"
