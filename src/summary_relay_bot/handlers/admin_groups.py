from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.group_settings import (
    GroupSettingsError,
    describe_groups,
    disable_group_summary,
    enable_group_summary,
    group_summary_settings,
    update_group_summary_interval,
)
from summary_relay_bot.telegram.guards import OwnerPrivateFilter


def build_router(*, owner_id: int) -> Router:
    router = Router(name="admin_groups")
    owner_private = OwnerPrivateFilter(owner_id)
    router.message.register(handle_groups, Command("groups"), owner_private)
    router.message.register(handle_enable_group, Command("enable_group"), owner_private)
    router.message.register(handle_disable_group, Command("disable_group"), owner_private)
    router.message.register(handle_set_interval, Command("set_interval"), owner_private)
    return router


async def handle_groups(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    async with session_scope(session_factory) as session:
        text = await describe_groups(session)
    await message.answer(text)


async def handle_enable_group(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    scheduler: object | None = None,
) -> None:
    text = getattr(message, "text", "") or ""
    parts = text.split()
    if len(parts) != 3:
        await message.answer("Usage: /enable_group <chat_id> <interval_minutes>")
        return
    try:
        chat_id = int(parts[1])
        interval = int(parts[2])
        async with session_scope(session_factory) as session:
            group = await enable_group_summary(session, chat_id=chat_id, interval_minutes=interval)
        if scheduler is not None and hasattr(scheduler, "upsert_summary_job"):
            scheduler.upsert_summary_job(chat_id, interval)
        await message.answer(f"Enabled summaries for {group.chat_id} every {interval} minutes.")
    except (ValueError, GroupSettingsError) as exc:
        await message.answer(f"Could not enable group: {exc}")


async def handle_disable_group(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    scheduler: object | None = None,
) -> None:
    text = getattr(message, "text", "") or ""
    parts = text.split()
    if len(parts) != 2:
        await message.answer("Usage: /disable_group <chat_id>")
        return
    try:
        chat_id = int(parts[1])
        async with session_scope(session_factory) as session:
            group = await disable_group_summary(session, chat_id=chat_id)
        if scheduler is not None and hasattr(scheduler, "remove_summary_job"):
            scheduler.remove_summary_job(chat_id)
        await message.answer(f"Disabled summaries for {group.chat_id}.")
    except (ValueError, GroupSettingsError) as exc:
        await message.answer(f"Could not disable group: {exc}")


async def handle_set_interval(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    scheduler: object | None = None,
) -> None:
    text = getattr(message, "text", "") or ""
    parts = text.split()
    if len(parts) != 3:
        await message.answer("Usage: /set_interval <chat_id> <interval_minutes>")
        return
    try:
        chat_id = int(parts[1])
        interval = int(parts[2])
        async with session_scope(session_factory) as session:
            group = await update_group_summary_interval(session, chat_id=chat_id, interval_minutes=interval)
            settings = await group_summary_settings(session, group=group)
            enabled = bool(settings and settings.enabled)
            scheduler_interval = settings.interval_minutes if settings is not None else interval
        if enabled and scheduler is not None and hasattr(scheduler, "upsert_summary_job"):
            scheduler.upsert_summary_job(chat_id, scheduler_interval)
        await message.answer(f"Updated {group.chat_id} interval to {interval} minutes.")
    except (ValueError, GroupSettingsError) as exc:
        await message.answer(f"Could not update interval: {exc}")
