from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from summary_relay_bot.db.models import GroupChat
from summary_relay_bot.db.repositories import (
    get_group_by_chat_id,
    list_groups,
    set_group_summary_enabled,
    set_group_summary_interval,
)


class GroupSettingsError(ValueError):
    pass


async def describe_groups(session: AsyncSession) -> str:
    groups = await list_groups(session)
    if not groups:
        return "No groups have been discovered yet. Add the bot to a group and send a message there first."
    lines = []
    for group in groups:
        status = "enabled" if group.summaries_enabled else "disabled"
        interval = group.summary_interval_minutes or "unset"
        title = group.title or "Untitled group"
        lines.append(f"{group.chat_id} — {title} — {status} — interval: {interval} min")
    return "\n".join(lines)


async def enable_group_summary(
    session: AsyncSession,
    *,
    chat_id: int,
    interval_minutes: int,
) -> GroupChat:
    if interval_minutes <= 0:
        raise GroupSettingsError("interval must be a positive number of minutes")
    group = await set_group_summary_enabled(
        session,
        chat_id=chat_id,
        enabled=True,
        interval_minutes=interval_minutes,
    )
    if group is None:
        raise GroupSettingsError("group is not known yet")
    return group


async def disable_group_summary(session: AsyncSession, *, chat_id: int) -> GroupChat:
    group = await set_group_summary_enabled(session, chat_id=chat_id, enabled=False)
    if group is None:
        raise GroupSettingsError("group is not known yet")
    return group


async def update_group_summary_interval(
    session: AsyncSession,
    *,
    chat_id: int,
    interval_minutes: int,
) -> GroupChat:
    if interval_minutes <= 0:
        raise GroupSettingsError("interval must be a positive number of minutes")
    group = await set_group_summary_interval(
        session,
        chat_id=chat_id,
        interval_minutes=interval_minutes,
    )
    if group is None:
        raise GroupSettingsError("group is not known yet")
    return group


async def enabled_groups(session: AsyncSession) -> Sequence[GroupChat]:
    return [group for group in await list_groups(session) if group.summaries_enabled]
