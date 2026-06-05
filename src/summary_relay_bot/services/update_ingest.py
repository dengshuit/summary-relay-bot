from __future__ import annotations

from dataclasses import asdict, is_dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.db.models import TelegramUpdate
from summary_relay_bot.db.repositories import get_or_create_raw_update, mark_raw_update_status


class UpdateIngestError(ValueError):
    pass


def object_to_payload(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "to_python"):
        return value.to_python()
    if hasattr(value, "__dict__"):
        return {
            key: nested_to_payload(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    raise UpdateIngestError("update cannot be serialized")


def nested_to_payload(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(key): nested_to_payload(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [nested_to_payload(item) for item in value]
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", exclude_none=True)
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "__dict__"):
        return {
            key: nested_to_payload(item)
            for key, item in vars(value).items()
            if not key.startswith("_")
        }
    return str(value)


def extract_update_id(update: Any, payload: dict[str, Any]) -> int:
    update_id = getattr(update, "update_id", None)
    if update_id is None:
        update_id = payload.get("update_id")
    if update_id is None:
        raise UpdateIngestError("update_id is required")
    return int(update_id)


async def persist_raw_update(
    session: AsyncSession,
    update: Any,
    *,
    status: str = "raw_persisted",
) -> tuple[TelegramUpdate, bool]:
    payload = object_to_payload(update)
    update_id = extract_update_id(update, payload)
    return await get_or_create_raw_update(session, update_id=update_id, payload=payload, status=status)


async def mark_update_handled(
    session: AsyncSession,
    raw_update: TelegramUpdate,
    status: str,
    *,
    error_type: str | None = None,
    error_message: str | None = None,
) -> None:
    await mark_raw_update_status(
        session,
        raw_update,
        status,
        error_type=error_type,
        error_message=error_message,
    )
