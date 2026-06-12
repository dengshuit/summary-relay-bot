from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from summary_relay_bot.db.models import AdminReplyMap, PrivateMessage, PrivateUser
from summary_relay_bot.web.deps import get_session_factory
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    PrivateRelayItemSchema,
    PrivateRelayReplyMapSchema,
    PrivateRelayStatsSchema,
    PrivateRelayUserSchema,
    PrivateRelaysResponse,
)


router = APIRouter(prefix="/private-relays", tags=["private-relays"])

_MAX_LIMIT = 1000
_PREVIEW_LIMIT = 300
_DIRECTIONS = frozenset({"incoming", "outgoing"})


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


def _preview(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) <= _PREVIEW_LIMIT:
        return value
    return f"{value[:_PREVIEW_LIMIT]}..."


def _relay_schema(message: PrivateMessage) -> PrivateRelayItemSchema:
    user = message.private_user
    return PrivateRelayItemSchema(
        id=message.id,
        private_user=PrivateRelayUserSchema(
            id=user.id,
            telegram_user_id=user.telegram_user_id,
            username=user.username,
            first_name=user.first_name,
            last_name=user.last_name,
        ),
        direction=message.direction,
        message_type=message.message_type,
        text_preview=_preview(message.text),
        caption_preview=_preview(message.caption),
        delivery_status=message.delivery_status,
        error_type=message.error_type,
        error_message=message.error_message,
        telegram_message_id=message.telegram_message_id,
        admin_message_id=message.admin_message_id,
        reply_maps=[
            PrivateRelayReplyMapSchema(
                source_kind=reply_map.source_kind,
                status=reply_map.status,
                admin_message_id=reply_map.admin_message_id,
            )
            for reply_map in message.reply_maps
        ],
        created_at=message.created_at,
    )


async def _stats(session: AsyncSession) -> PrivateRelayStatsSchema:
    rows = await session.execute(
        select(PrivateMessage.delivery_status, func.count(PrivateMessage.id)).group_by(
            PrivateMessage.delivery_status
        )
    )
    counts = {status: int(count) for status, count in rows}
    return PrivateRelayStatsSchema(
        total=sum(counts.values()),
        sent=counts.get("sent", 0),
        partial_failed=counts.get("partial_failed", 0),
        failed=counts.get("failed", 0),
        blocked=counts.get("blocked", 0),
    )


@router.get("", response_model=PrivateRelaysResponse)
async def get_private_relays(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    direction: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    q: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query()] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> PrivateRelaysResponse | JSONResponse:
    cursor_id = _decode_cursor(cursor)
    if cursor is not None and cursor_id is None:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message="cursor is invalid",
        )
    if direction is not None and direction not in _DIRECTIONS:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message="direction is not supported",
        )

    normalized_limit = _normalize_limit(limit)
    async with session_factory() as session:
        statement = (
            select(PrivateMessage)
            .join(PrivateUser, PrivateUser.id == PrivateMessage.private_user_id)
            .options(
                selectinload(PrivateMessage.private_user),
                selectinload(PrivateMessage.reply_maps),
            )
            .order_by(PrivateMessage.id.desc())
        )
        if cursor_id is not None:
            statement = statement.where(PrivateMessage.id < cursor_id)
        if direction is not None:
            statement = statement.where(PrivateMessage.direction == direction)
        if status is not None:
            statement = statement.where(PrivateMessage.delivery_status == status)
        if q is not None and q.strip():
            needle = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    PrivateUser.username.ilike(needle),
                    PrivateUser.first_name.ilike(needle),
                    PrivateUser.last_name.ilike(needle),
                    cast(PrivateUser.telegram_user_id, String).ilike(needle),
                    PrivateMessage.text.ilike(needle),
                    PrivateMessage.caption.ilike(needle),
                )
            )
        messages = (
            await session.scalars(statement.limit(normalized_limit + 1))
        ).unique().all()
        stats = await _stats(session)

    has_more = len(messages) > normalized_limit
    messages = messages[:normalized_limit]
    return PrivateRelaysResponse(
        items=[_relay_schema(message) for message in messages],
        next_cursor=str(messages[-1].id) if has_more and messages else None,
        stats=stats,
    )
