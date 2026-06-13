from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from summary_relay_bot.db.models import GroupChat, GroupSummarySettings, SummaryUserbot
from summary_relay_bot.db.repositories import get_group_by_chat_id, list_groups
from summary_relay_bot.services.runtime_config import set_group_summary_settings


class GroupSettingsError(ValueError):
    pass


DEFAULT_DISABLED_INTERVAL_MINUTES = 300
DEFAULT_TIMEZONE = "UTC"


async def describe_groups(session: AsyncSession) -> str:
    groups = await list_groups(session)
    if not groups:
        return "No groups have been discovered yet. Add the bot to a group and send a message there first."
    lines = []
    for group in groups:
        settings = await group_summary_settings(session, group=group)
        status = "enabled" if settings and settings.enabled else "disabled"
        interval = settings.interval_minutes if settings else "unset"
        title = group.title or "Untitled group"
        lines.append(f"{group.chat_id} — {title} — {status} — interval: {interval} min")
    return "\n".join(lines)


async def group_summary_settings(
    session: AsyncSession,
    *,
    group: GroupChat,
) -> GroupSummarySettings | None:
    settings = await session.scalar(
        select(GroupSummarySettings)
        .options(selectinload(GroupSummarySettings.summary_profile))
        .where(GroupSummarySettings.id == group.id)
    )
    return settings.summary_settings if settings is not None else None


async def enable_group_summary(
    session: AsyncSession,
    *,
    chat_id: int,
    interval_minutes: int,
) -> GroupChat:
    if interval_minutes <= 0:
        raise GroupSettingsError("interval must be a positive number of minutes")
    group = await get_group_by_chat_id(session, chat_id)
    if group is None:
        raise GroupSettingsError("group is not known yet")
    await set_group_summary_settings(
        session,
        group=group,
        enabled=True,
        interval_minutes=interval_minutes,
    )
    return group


async def disable_group_summary(session: AsyncSession, *, chat_id: int) -> GroupChat:
    group = await get_group_by_chat_id(session, chat_id)
    if group is None:
        raise GroupSettingsError("group is not known yet")
    settings = await group_summary_settings(session, group=group)
    interval = settings.interval_minutes if settings is not None else DEFAULT_DISABLED_INTERVAL_MINUTES
    await set_group_summary_settings(
        session,
        group=group,
        enabled=False,
        interval_minutes=interval,
        summary_profile=settings.summary_profile if settings is not None else None,
        timezone=settings.timezone if settings is not None else DEFAULT_TIMEZONE,
    )
    return group


async def update_group_summary_interval(
    session: AsyncSession,
    *,
    chat_id: int,
    interval_minutes: int,
) -> GroupChat:
    if interval_minutes <= 0:
        raise GroupSettingsError("interval must be a positive number of minutes")
    group = await get_group_by_chat_id(session, chat_id)
    if group is None:
        raise GroupSettingsError("group is not known yet")
    settings = await group_summary_settings(session, group=group)
    await set_group_summary_settings(
        session,
        group=group,
        enabled=settings.enabled if settings is not None else False,
        interval_minutes=interval_minutes,
        summary_profile=settings.summary_profile if settings is not None else None,
        timezone=settings.timezone if settings is not None else DEFAULT_TIMEZONE,
    )
    return group


async def enabled_group_settings(session: AsyncSession) -> Sequence[GroupSummarySettings]:
    enabled_userbot = await session.scalar(select(SummaryUserbot).where(SummaryUserbot.enabled.is_(True)))
    statement = select(GroupSummarySettings).where(GroupSummarySettings.enabled.is_(True))
    if enabled_userbot is not None:
        statement = statement.where(GroupSummarySettings.userbot_id == enabled_userbot.id)
    result = await session.scalars(statement.order_by(GroupSummarySettings.id))
    return result.all()
