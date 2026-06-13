from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.models import GroupChat, utcnow
from summary_relay_bot.db.repositories import latest_group_messages
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.llm.client import PrivacyAwareSummaryClient, SummaryLLMError
from summary_relay_bot.services.runtime_config import RuntimeConfigError, load_summary_profile_runtime_config
from summary_relay_bot.services.secrets import SecretError, SecretService


SUMMARY_TEST_TASK_MAX_MESSAGES = 50
SUMMARY_TEST_TASK_MAX_TASKS = 5
SUMMARY_TEST_TASK_TERMINAL_TTL = timedelta(minutes=30)

SUMMARY_TEST_TASK_TERMINAL_STATUSES = frozenset({"succeeded", "failed", "canceled"})


@dataclass(frozen=True, slots=True)
class SummaryTestTaskView:
    id: str
    group_id: int
    chat_id: int
    status: str
    step: str
    message_count: int | None
    sequence_range: str | None
    summary_text: str | None
    error_type: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


@dataclass(slots=True)
class _SummaryTestTaskState:
    id: str
    group_id: int
    chat_id: int
    status: str
    step: str
    message_count: int | None
    sequence_range: str | None
    summary_text: str | None
    error_type: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None


@dataclass(slots=True)
class _SummaryTestTaskEntry:
    state: _SummaryTestTaskState
    handle: asyncio.Task[None] | None = None


class SummaryTestTaskRegistryFullError(RuntimeError):
    pass


class SummaryTestTaskRegistry:
    def __init__(
        self,
        *,
        max_tasks: int = SUMMARY_TEST_TASK_MAX_TASKS,
        terminal_ttl: timedelta = SUMMARY_TEST_TASK_TERMINAL_TTL,
    ) -> None:
        self.max_tasks = max_tasks
        self.terminal_ttl = terminal_ttl
        self._entries: dict[str, _SummaryTestTaskEntry] = {}
        self._lock = asyncio.Lock()

    async def create_task(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        secret_service: SecretService,
        group_id: int,
        chat_id: int,
    ) -> SummaryTestTaskView:
        now = utcnow()
        state = _SummaryTestTaskState(
            id=uuid4().hex,
            group_id=group_id,
            chat_id=chat_id,
            status="pending",
            step="submitted",
            message_count=None,
            sequence_range=None,
            summary_text=None,
            error_type=None,
            error_message=None,
            created_at=now,
        )
        async with self._lock:
            self._cleanup_locked(now)
            self._evict_terminal_until_room_locked()
            if len(self._entries) >= self.max_tasks:
                raise SummaryTestTaskRegistryFullError("summary test task registry is full")
            self._entries[state.id] = _SummaryTestTaskEntry(state=state)

        handle = asyncio.create_task(
            self._run_task(
                task_id=state.id,
                session_factory=session_factory,
                secret_service=secret_service,
                group_id=group_id,
            ),
            name=f"summary-test-task:{group_id}:{state.id}",
        )
        async with self._lock:
            entry = self._entries.get(state.id)
            if entry is not None:
                entry.handle = handle
                return self._view(entry.state)
        return self._view(state)

    async def get_task(self, task_id: str) -> SummaryTestTaskView | None:
        async with self._lock:
            self._cleanup_locked(utcnow())
            entry = self._entries.get(task_id)
            if entry is None:
                return None
            return self._view(entry.state)

    async def cancel_task(self, task_id: str) -> SummaryTestTaskView | None:
        handle: asyncio.Task[None] | None = None
        async with self._lock:
            self._cleanup_locked(utcnow())
            entry = self._entries.get(task_id)
            if entry is None:
                return None
            if entry.state.status not in SUMMARY_TEST_TASK_TERMINAL_STATUSES:
                self._finish_locked(entry.state, status="canceled", error_type=None, error_message=None)
                handle = entry.handle
            view = self._view(entry.state)
        if handle is not None and not handle.done():
            handle.cancel()
        return view

    def _cleanup_locked(self, now: datetime) -> None:
        expired_task_ids = [
            task_id
            for task_id, entry in self._entries.items()
            if entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES
            and entry.state.finished_at is not None
            and entry.state.finished_at + self.terminal_ttl <= now
        ]
        for task_id in expired_task_ids:
            self._entries.pop(task_id, None)

    def _evict_terminal_until_room_locked(self) -> None:
        while len(self._entries) >= self.max_tasks:
            terminal_entries = [
                entry
                for entry in self._entries.values()
                if entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES
            ]
            if not terminal_entries:
                return
            oldest = min(terminal_entries, key=lambda entry: entry.state.finished_at or entry.state.created_at)
            self._entries.pop(oldest.state.id, None)

    async def _run_task(
        self,
        *,
        task_id: str,
        session_factory: async_sessionmaker[AsyncSession],
        secret_service: SecretService,
        group_id: int,
    ) -> None:
        try:
            if not await self._mark_running(task_id, step="queued"):
                return
            async with session_scope(session_factory) as session:
                group = await session.get(GroupChat, group_id)
                if group is None:
                    await self._mark_failed(
                        task_id,
                        error_type="not_found",
                        error_message="group not found",
                    )
                    return
                if not await self._mark_running(task_id, step="running"):
                    return
                runtime_profile = await load_summary_profile_runtime_config(
                    session,
                    secret_service=secret_service,
                    group=group,
                )
                messages = list(
                    await latest_group_messages(
                        session,
                        group=group,
                        limit=SUMMARY_TEST_TASK_MAX_MESSAGES,
                    )
                )
                sequence_range = _sequence_range(messages[0].id, messages[-1].id) if messages else None
                if not await self._set_message_scope(
                    task_id,
                    message_count=len(messages),
                    sequence_range=sequence_range,
                ):
                    return
                if not messages:
                    await self._mark_succeeded(
                        task_id,
                        summary_text="当前群聊暂无可用于测试的消息。",
                    )
                    return

                if not await self._mark_running(task_id, step="generating"):
                    return
                summary_text = await PrivacyAwareSummaryClient(runtime_profile).summarize_group_messages(
                    group_title=group.title,
                    group_messages=messages,
                )
                await self._mark_succeeded(task_id, summary_text=summary_text)
        except asyncio.CancelledError:
            await self._mark_canceled(task_id)
        except (RuntimeConfigError, SecretError) as exc:
            await self._mark_failed(
                task_id,
                error_type="runtime_config_error",
                error_message=str(exc),
            )
        except SummaryLLMError as exc:
            await self._mark_failed(
                task_id,
                error_type="llm_failed",
                error_message=str(exc),
            )
        except Exception:
            await self._mark_failed(
                task_id,
                error_type="internal_error",
                error_message="summary test task failed",
            )

    async def _mark_running(self, task_id: str, *, step: str) -> bool:
        async with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES:
                return False
            entry.state.status = "running"
            entry.state.step = step
            if entry.state.started_at is None:
                entry.state.started_at = utcnow()
            return True

    async def _set_message_scope(
        self,
        task_id: str,
        *,
        message_count: int,
        sequence_range: str | None,
    ) -> bool:
        async with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES:
                return False
            entry.state.message_count = message_count
            entry.state.sequence_range = sequence_range
            return True

    async def _mark_succeeded(self, task_id: str, *, summary_text: str) -> bool:
        async with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES:
                return False
            entry.state.summary_text = summary_text
            self._finish_locked(entry.state, status="succeeded", error_type=None, error_message=None)
            return True

    async def _mark_failed(self, task_id: str, *, error_type: str, error_message: str) -> bool:
        async with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES:
                return False
            self._finish_locked(
                entry.state,
                status="failed",
                error_type=error_type,
                error_message=error_message,
            )
            return True

    async def _mark_canceled(self, task_id: str) -> bool:
        async with self._lock:
            entry = self._entries.get(task_id)
            if entry is None or entry.state.status in SUMMARY_TEST_TASK_TERMINAL_STATUSES:
                return False
            self._finish_locked(entry.state, status="canceled", error_type=None, error_message=None)
            return True

    def _finish_locked(
        self,
        state: _SummaryTestTaskState,
        *,
        status: str,
        error_type: str | None,
        error_message: str | None,
    ) -> None:
        state.status = status
        state.step = "completed"
        state.error_type = error_type
        state.error_message = error_message
        state.finished_at = utcnow()

    def _view(self, state: _SummaryTestTaskState) -> SummaryTestTaskView:
        return SummaryTestTaskView(
            id=state.id,
            group_id=state.group_id,
            chat_id=state.chat_id,
            status=state.status,
            step=state.step,
            message_count=state.message_count,
            sequence_range=state.sequence_range,
            summary_text=state.summary_text,
            error_type=state.error_type,
            error_message=state.error_message,
            created_at=state.created_at,
            started_at=state.started_at,
            finished_at=state.finished_at,
        )


def _sequence_range(start_sequence: int, end_sequence: int) -> str:
    return f"{start_sequence}-{end_sequence}"
