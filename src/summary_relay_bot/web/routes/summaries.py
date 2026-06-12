from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import String, cast, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.models import GroupChat, LLMProvider, SummaryJob, SummaryProfile, SummaryResult
from summary_relay_bot.web.deps import get_session_factory
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import HistoricalSummaryListResponse, HistoricalSummarySchema


router = APIRouter(prefix="/summaries", tags=["summaries"])

_MAX_LIMIT = 100
_SUMMARY_STATUSES = frozenset({"pending", "running", "succeeded", "failed", "blocked"})


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
    if value is None or value.strip() == "":
        return None
    normalized = value.strip()
    if " " in normalized and "+" not in normalized:
        normalized = normalized.replace(" ", "+")
    if normalized.endswith("Z"):
        normalized = f"{normalized[:-1]}+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field_name} is invalid") from exc


def _sequence_range(job: SummaryJob, result: SummaryResult | None) -> str | None:
    start = result.interval_start_sequence if result is not None else job.starting_sequence
    end = result.interval_end_sequence if result is not None else job.cutoff_sequence
    if end is None:
        return None
    return f"{start + 1}-{end}"


def _summary_schema(
    job: SummaryJob,
    group: GroupChat,
    result: SummaryResult | None,
    provider: LLMProvider | None,
    profile: SummaryProfile | None,
) -> HistoricalSummarySchema:
    return HistoricalSummarySchema(
        id=result.id if result is not None else job.id,
        job_id=job.id,
        group_id=group.id,
        group_title=group.title,
        group_username=group.username,
        chat_id=job.chat_id,
        status=job.status,
        trigger_type=job.trigger_type,
        sequence_range=_sequence_range(job, result),
        model=(result.model if result is not None else job.model),
        provider=provider.name if provider is not None else None,
        profile_name=profile.name if profile is not None else None,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_type=job.error_type,
        error_message=job.error_message,
        content=result.summary_text if result is not None else None,
    )


@router.get("", response_model=HistoricalSummaryListResponse)
async def get_summaries(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    q: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    group_id: Annotated[int | None, Query()] = None,
    from_: Annotated[str | None, Query(alias="from")] = None,
    to: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query()] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> HistoricalSummaryListResponse | JSONResponse:
    cursor_id = _decode_cursor(cursor)
    if cursor is not None and cursor_id is None:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message="cursor is invalid",
        )
    if status is not None and status not in _SUMMARY_STATUSES:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message="status is not supported",
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
        statement = (
            select(SummaryJob, GroupChat, SummaryResult, LLMProvider, SummaryProfile)
            .join(GroupChat, GroupChat.id == SummaryJob.group_id)
            .outerjoin(SummaryResult, SummaryResult.job_id == SummaryJob.id)
            .outerjoin(LLMProvider, LLMProvider.id == SummaryJob.llm_provider_id)
            .outerjoin(SummaryProfile, SummaryProfile.id == SummaryJob.summary_profile_id)
            .order_by(SummaryJob.id.desc())
        )
        if cursor_id is not None:
            statement = statement.where(SummaryJob.id < cursor_id)
        if status is not None:
            statement = statement.where(SummaryJob.status == status)
        if group_id is not None:
            statement = statement.where(SummaryJob.group_id == group_id)
        if from_dt is not None:
            statement = statement.where(SummaryJob.created_at >= from_dt)
        if to_dt is not None:
            statement = statement.where(SummaryJob.created_at <= to_dt)
        if q is not None and q.strip():
            needle = f"%{q.strip()}%"
            statement = statement.where(
                or_(
                    GroupChat.title.ilike(needle),
                    GroupChat.username.ilike(needle),
                    cast(GroupChat.chat_id, String).ilike(needle),
                )
            )
        rows = (await session.execute(statement.limit(normalized_limit + 1))).all()

    has_more = len(rows) > normalized_limit
    rows = rows[:normalized_limit]
    return HistoricalSummaryListResponse(
        items=[
            _summary_schema(job, group, result, provider, profile)
            for job, group, result, provider, profile in rows
        ],
        next_cursor=str(rows[-1][0].id) if has_more and rows else None,
    )
