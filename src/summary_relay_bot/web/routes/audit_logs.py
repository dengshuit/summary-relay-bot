from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.models import AuditLog
from summary_relay_bot.web.deps import get_session_factory
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import AuditLogListResponse, AuditLogSchema


router = APIRouter(prefix="/audit-logs", tags=["audit-logs"])

_MAX_LIMIT = 100
_SECRET_KEYS = frozenset(
    {
        "api_key",
        "bot_token",
        "llm_api_key",
        "settings_encryption_key",
        "webui_admin_token",
        "token",
    }
)


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_LIMIT))


def _decode_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    try:
        parsed = int(cursor)
    except ValueError:
        return None
    return parsed if parsed > 0 else None


def _parse_datetime(value: str | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip()
    if normalized == "":
        return None
    if " " in normalized and "+" not in normalized:
        normalized = normalized.replace(" ", "+")
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} is invalid") from exc


def _safe_audit_value(value: Any) -> Any:
    if isinstance(value, dict):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in _SECRET_KEYS or normalized_key.endswith("_token") or normalized_key.endswith("_key"):
                redacted[key] = "configured" if item else "not_configured"
            else:
                redacted[key] = _safe_audit_value(item)
        return redacted
    if isinstance(value, list):
        return [_safe_audit_value(item) for item in value]
    return value


def _audit_log_schema(audit_log: AuditLog) -> AuditLogSchema:
    return AuditLogSchema(
        id=audit_log.id,
        actor=audit_log.actor,
        action=audit_log.action,
        entity_type=audit_log.entity_type,
        entity_id=audit_log.entity_id,
        redacted_before=_safe_audit_value(audit_log.redacted_before),
        redacted_after=_safe_audit_value(audit_log.redacted_after),
        created_at=audit_log.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
async def get_audit_logs(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    entity_type: Annotated[str | None, Query()] = None,
    action: Annotated[str | None, Query()] = None,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query()] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> AuditLogListResponse | JSONResponse:
    cursor_id = _decode_cursor(cursor)
    if cursor is not None and cursor_id is None:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message="cursor is invalid",
        )

    try:
        from_dt = _parse_datetime(from_, "from")
        to_dt = _parse_datetime(to, "to")
    except ValueError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )

    normalized_limit = _normalize_limit(limit)
    async with session_factory() as session:
        statement = select(AuditLog).order_by(AuditLog.id.desc())
        if entity_type is not None:
            statement = statement.where(AuditLog.entity_type == entity_type)
        if action is not None:
            statement = statement.where(AuditLog.action == action)
        if from_dt is not None:
            statement = statement.where(AuditLog.created_at >= from_dt)
        if to_dt is not None:
            statement = statement.where(AuditLog.created_at <= to_dt)
        if cursor_id is not None:
            statement = statement.where(AuditLog.id < cursor_id)

        rows = (await session.scalars(statement.limit(normalized_limit + 1))).all()

    has_more = len(rows) > normalized_limit
    rows = rows[:normalized_limit]
    return AuditLogListResponse(
        items=[_audit_log_schema(row) for row in rows],
        next_cursor=str(rows[-1].id) if has_more and rows else None,
    )
