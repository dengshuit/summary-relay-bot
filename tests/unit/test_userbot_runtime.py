from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select

from summary_relay_bot.db.models import SummaryEntity, SummaryMessage, SummaryUserbot
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import set_group_summary_settings
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.userbot_auth import create_summary_userbot
from summary_relay_bot.services.userbot_ingestion import DeletedMessage, DiscoveredDialog, EditedMessage, IncomingMessage
from summary_relay_bot.services.userbot_runtime import SummaryUserbotRuntimeManager


class FakeCollector:
    def __init__(self) -> None:
        self.handlers = None
        self.started = asyncio.Event()
        self.disconnected = asyncio.Event()
        self.disconnect_called = False
        self.fail_with: Exception | None = None

    async def run_until_disconnected(self) -> None:
        self.started.set()
        if self.fail_with is not None:
            raise self.fail_with
        await self.disconnected.wait()

    async def disconnect(self) -> None:
        self.disconnect_called = True
        self.disconnected.set()


def secret_service() -> SecretService:
    return SecretService(SecretService.generate_key())


async def _manager_with_collector(session_factory, service: SecretService, collector: FakeCollector):
    observed: dict[str, object] = {}

    async def discover_dialogs(runtime_config):
        observed["discovery_api_id"] = runtime_config.api_id
        return [DiscoveredDialog(telegram_entity_id=-1001, entity_type="megagroup", title="Runtime group")]

    def create_collector(config, userbot_id, handlers):
        observed["collector_api_id"] = config.api_id
        observed["collector_session"] = config.session_string
        observed["collector_userbot_id"] = userbot_id
        collector.handlers = handlers
        return collector

    manager = SummaryUserbotRuntimeManager(
        session_factory=session_factory,
        secret_service=service,
        discover_dialogs=discover_dialogs,
        create_update_collector=create_collector,
    )
    return manager, observed


async def _create_authorized_userbot(session_factory, service: SecretService) -> int:
    async with session_scope(session_factory) as session:
        userbot = await create_summary_userbot(
            session,
            secret_service=service,
            name="Main userbot",
            api_id=12345,
            api_hash="api-hash-secret",
            phone_number="+15550001111",
            session_string="string-session-secret",
            enabled=True,
        )
        return userbot.id


async def _enabled_group(session_factory) -> SummaryEntity:
    async with session_scope(session_factory) as session:
        group = await session.scalar(select(SummaryEntity).where(SummaryEntity.chat_id == -1001))
        assert group is not None
        await set_group_summary_settings(
            session,
            group=group,
            enabled=True,
            interval_minutes=30,
        )
        return group


async def test_summary_userbot_runtime_starts_discovery_and_update_collector(session_factory) -> None:
    service = secret_service()
    userbot_id = await _create_authorized_userbot(session_factory, service)
    collector = FakeCollector()
    manager, observed = await _manager_with_collector(session_factory, service, collector)

    await manager.start_from_db()
    await collector.started.wait()

    async with session_factory() as session:
        group = await session.scalar(select(SummaryEntity).where(SummaryEntity.chat_id == -1001))
        userbot = await session.get(SummaryUserbot, userbot_id)
    assert observed == {
        "discovery_api_id": 12345,
        "collector_api_id": 12345,
        "collector_session": "string-session-secret",
        "collector_userbot_id": userbot_id,
    }
    assert group is not None
    assert group.enabled is False
    assert userbot is not None
    assert userbot.runtime_status == "running"

    await manager.stop()
    assert collector.disconnect_called is True


async def test_summary_userbot_runtime_does_not_start_second_collector_while_running(session_factory) -> None:
    service = secret_service()
    await _create_authorized_userbot(session_factory, service)
    collector = FakeCollector()
    created_count = 0

    async def discover_dialogs(_runtime_config):
        return [DiscoveredDialog(telegram_entity_id=-1001, entity_type="megagroup", title="Runtime group")]

    def create_collector(_config, _userbot_id, handlers):
        nonlocal created_count
        created_count += 1
        collector.handlers = handlers
        return collector

    manager = SummaryUserbotRuntimeManager(
        session_factory=session_factory,
        secret_service=service,
        discover_dialogs=discover_dialogs,
        create_update_collector=create_collector,
    )

    await manager.start_from_db()
    await collector.started.wait()
    await manager.start_from_db()

    assert created_count == 1
    await manager.stop()


async def test_summary_userbot_runtime_ingests_only_enabled_group_updates(session_factory) -> None:
    service = secret_service()
    userbot_id = await _create_authorized_userbot(session_factory, service)
    collector = FakeCollector()
    manager, _observed = await _manager_with_collector(session_factory, service, collector)
    await manager.start_from_db()
    await collector.started.wait()
    assert collector.handlers is not None

    ignored = IncomingMessage(
        userbot_id=userbot_id,
        telegram_entity_id=-1001,
        telegram_message_id=10,
        message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
        text="disabled",
    )
    await collector.handlers.on_message(ignored)
    async with session_factory() as session:
        assert (await session.scalars(select(SummaryMessage))).all() == []

    await _enabled_group(session_factory)
    await collector.handlers.on_message(
        IncomingMessage(
            userbot_id=userbot_id,
            telegram_entity_id=-1001,
            telegram_message_id=11,
            message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
            text="enabled",
            sender_user_id=42,
            sender_username="alice",
            sender_display_name="Alice",
        )
    )

    async with session_factory() as session:
        [message] = (await session.scalars(select(SummaryMessage))).all()
    assert message.telegram_message_id == 11
    assert message.text == "enabled"
    assert message.summary_content == "enabled"
    assert message.sender_username == "alice"

    await manager.stop()


async def test_summary_userbot_runtime_routes_edit_and_delete_updates(session_factory) -> None:
    service = secret_service()
    userbot_id = await _create_authorized_userbot(session_factory, service)
    collector = FakeCollector()
    manager, _observed = await _manager_with_collector(session_factory, service, collector)
    await manager.start_from_db()
    await collector.started.wait()
    assert collector.handlers is not None
    await _enabled_group(session_factory)

    await collector.handlers.on_message(
        IncomingMessage(
            userbot_id=userbot_id,
            telegram_entity_id=-1001,
            telegram_message_id=12,
            message_date=datetime(2026, 6, 13, tzinfo=timezone.utc),
            text="before",
        )
    )
    await collector.handlers.on_edit(
        EditedMessage(
            userbot_id=userbot_id,
            telegram_entity_id=-1001,
            telegram_message_id=12,
            edited_at=datetime(2026, 6, 13, 1, tzinfo=timezone.utc),
            text="after",
        )
    )
    await collector.handlers.on_delete(
        DeletedMessage(
            userbot_id=userbot_id,
            telegram_entity_id=-1001,
            telegram_message_ids=[12],
            deleted_at=datetime(2026, 6, 13, 2, tzinfo=timezone.utc),
        )
    )

    async with session_factory() as session:
        [message] = (await session.scalars(select(SummaryMessage))).all()
    assert message.text == "after"
    assert message.summary_content == "after"
    assert message.edited_at is not None
    assert message.deleted_at is not None

    await manager.stop()


async def test_summary_userbot_runtime_marks_failed_when_collector_fails(session_factory) -> None:
    service = secret_service()
    userbot_id = await _create_authorized_userbot(session_factory, service)
    collector = FakeCollector()
    collector.fail_with = RuntimeError("session exploded")
    manager, _observed = await _manager_with_collector(session_factory, service, collector)

    await manager.start_from_db()
    task = manager._collector_task
    assert task is not None
    await task

    async with session_factory() as session:
        userbot = await session.get(SummaryUserbot, userbot_id)
    assert userbot is not None
    assert userbot.runtime_status == "failed"
    assert userbot.last_error_type == "RuntimeError"
    assert userbot.last_error_message == "summary userbot update collector failed"


async def test_summary_userbot_runtime_stop_disconnects_collector_and_marks_stopped(session_factory) -> None:
    service = secret_service()
    userbot_id = await _create_authorized_userbot(session_factory, service)
    collector = FakeCollector()
    manager, _observed = await _manager_with_collector(session_factory, service, collector)
    await manager.start_from_db()
    await collector.started.wait()

    await manager.stop()

    async with session_factory() as session:
        userbot = await session.get(SummaryUserbot, userbot_id)
    assert collector.disconnect_called is True
    assert userbot is not None
    assert userbot.runtime_status == "stopped"
    assert userbot.last_stopped_at is not None
