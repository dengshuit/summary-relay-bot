from __future__ import annotations

from collections.abc import Mapping
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.models import (
    AuditLog,
    BotInstance,
    GroupChat,
    GroupSummarySettings,
    SummaryJob,
    SummaryProfile,
    utcnow,
)
from summary_relay_bot.services.telegram_runtime import TelegramRuntimeManager
from summary_relay_bot.web.deps import get_session_factory, get_telegram_runtime, get_telegram_startup
from summary_relay_bot.web.schemas import (
    DashboardBotSchema,
    DashboardResponse,
    DefaultProfileSchema,
    GroupCountsSchema,
    RecentAuditLogSchema,
    Summary24hSchema,
    TelegramStartupSchema,
)


router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _telegram_startup_schema(telegram_startup: object) -> TelegramStartupSchema:
    if isinstance(telegram_startup, Mapping):
        return TelegramStartupSchema(
            status=str(telegram_startup.get("status", "unknown")),
            detail=telegram_startup.get("detail"),
        )
    return TelegramStartupSchema(
        status=str(getattr(telegram_startup, "status", "unknown")),
        detail=getattr(telegram_startup, "detail", None),
    )


def _telegram_runtime_schema(
    telegram_startup: object,
    telegram_runtime: TelegramRuntimeManager | None,
) -> TelegramStartupSchema:
    if telegram_runtime is None:
        return _telegram_startup_schema(telegram_startup)
    state = telegram_runtime.state_snapshot()
    return TelegramStartupSchema(status=state.status, detail=state.detail)


def _bot_schema(bot: BotInstance | None) -> DashboardBotSchema | None:
    if bot is None:
        return None
    return DashboardBotSchema(
        id=bot.id,
        name=bot.name,
        enabled=bot.enabled,
        status=bot.status,
        needs_restart=bot.needs_restart,
        telegram_bot_id=bot.telegram_bot_id,
        telegram_username=bot.telegram_username,
        last_validated_at=bot.last_validated_at,
    )


def _default_profile_schema(profile: SummaryProfile | None) -> DefaultProfileSchema | None:
    if profile is None:
        return None
    return DefaultProfileSchema(
        id=profile.id,
        name=profile.name,
        enabled=profile.enabled,
        llm_provider_id=profile.llm_provider_id,
        prompt_version=profile.prompt_version,
    )


async def _summary_24h(session: AsyncSession) -> Summary24hSchema:
    window_start = utcnow() - timedelta(hours=24)
    rows = await session.execute(
        select(SummaryJob.status, func.count(SummaryJob.id))
        .where(SummaryJob.created_at >= window_start)
        .group_by(SummaryJob.status)
    )
    counts = {status: int(count) for status, count in rows}
    total = sum(counts.values())
    return Summary24hSchema(
        total=total,
        succeeded=counts.get("succeeded", 0),
        failed=counts.get("failed", 0),
    )


async def _group_counts(session: AsyncSession) -> GroupCountsSchema:
    total = await session.scalar(select(func.count(GroupChat.id)))
    enabled = await session.scalar(
        select(func.count(GroupSummarySettings.id)).where(GroupSummarySettings.enabled.is_(True))
    )
    return GroupCountsSchema(total=int(total or 0), enabled=int(enabled or 0))


async def _recent_audit_logs(session: AsyncSession) -> list[RecentAuditLogSchema]:
    audit_logs = (
        await session.scalars(
            select(AuditLog).order_by(AuditLog.created_at.desc()).limit(5)
        )
    ).all()
    return [
        RecentAuditLogSchema(
            id=audit_log.id,
            actor=audit_log.actor,
            action=audit_log.action,
            entity_type=audit_log.entity_type,
            entity_id=audit_log.entity_id,
            created_at=audit_log.created_at,
        )
        for audit_log in audit_logs
    ]


async def _restart_pending(session: AsyncSession) -> list[str]:
    bot_instances = (
        await session.scalars(
            select(BotInstance)
            .where(BotInstance.needs_restart.is_(True))
            .order_by(BotInstance.id)
        )
    ).all()
    return [f"bot_instance:{bot_instance.id}" for bot_instance in bot_instances]


@router.get("", response_model=DashboardResponse)
async def get_dashboard(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    telegram_startup: Annotated[object, Depends(get_telegram_startup)],
    telegram_runtime: Annotated[TelegramRuntimeManager | None, Depends(get_telegram_runtime)],
) -> DashboardResponse:
    async with session_factory() as session:
        bot = await session.scalar(
            select(BotInstance)
            .where(BotInstance.enabled.is_(True))
            .order_by(BotInstance.id)
            .limit(1)
        )
        default_profile = await session.scalar(
            select(SummaryProfile)
            .where(SummaryProfile.is_default.is_(True))
            .order_by(SummaryProfile.id)
            .limit(1)
        )
        return DashboardResponse(
            telegram_startup=_telegram_runtime_schema(telegram_startup, telegram_runtime),
            bot=_bot_schema(bot),
            groups=await _group_counts(session),
            default_profile=_default_profile_schema(default_profile),
            summary_24h=await _summary_24h(session),
            restart_pending=await _restart_pending(session),
            recent_audit_logs=await _recent_audit_logs(session),
        )
