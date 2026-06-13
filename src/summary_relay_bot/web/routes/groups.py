from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import JSONResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from summary_relay_bot.db.models import (
    GroupChat,
    LLMProvider,
    SummaryJob,
    SummaryProfile,
)
from summary_relay_bot.db.repositories import (
    get_active_summary_job,
    latest_summary_delivery_attempt,
    get_summary_job_for_group,
    recent_summary_jobs_for_group,
)
from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    RuntimeConfigError,
    SummaryProfileNotFoundError,
    create_audit_log,
    default_summary_profile,
    get_summary_profile,
    set_group_summary_settings,
)
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.summary_jobs import (
    SummaryJobConflictError,
    SummaryJobNotFoundError,
    SummaryJobResultView,
    SummaryJobView,
    create_manual_summary_job,
    get_summary_job_status,
    schedule_manual_summary_job,
)
from summary_relay_bot.services.summary_notifications import SummaryNotificationDispatcher
from summary_relay_bot.services.summary_test_tasks import (
    SummaryTestTaskRegistry,
    SummaryTestTaskRegistryFullError,
    SummaryTestTaskView,
)
from summary_relay_bot.services.userbot_auth import UserbotConfigError
from summary_relay_bot.services.userbot_ingestion import (
    DialogDiscoveryProvider,
    refresh_enabled_userbot_dialogs,
)
from summary_relay_bot.web.deps import (
    get_actor,
    get_secret_service,
    get_session_factory,
    get_summary_notification_dispatcher,
    get_summary_test_task_registry,
    get_userbot_dialog_discovery_provider,
)
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    EffectiveSummaryProfileSchema,
    GroupDetailSchema,
    GroupDiscoveryRefreshResponse,
    GroupLastSummarySchema,
    GroupListItemSchema,
    GroupListResponse,
    GroupSummarySettingsSchema,
    GroupSummarySettingsUpdateRequest,
    GroupSummaryStateSchema,
    SummaryDeliverySchema,
    SummaryJobResultSchema,
    SummaryJobSchema,
    SummaryTestTaskSchema,
    TriggerSummaryJobResponse,
    TriggerSummaryTestTaskResponse,
)


router = APIRouter(prefix="/groups", tags=["groups"])

_MAX_LIMIT = 100
_DEFAULT_INTERVAL_MINUTES = 300
_DEFAULT_TIMEZONE = "UTC"
_SUMMARY_JOB_STATUSES = frozenset({"pending", "running", "succeeded", "failed", "blocked"})


def _normalize_limit(limit: int) -> int:
    return max(1, min(limit, _MAX_LIMIT))


def _model_data(model) -> dict:
    dump = getattr(model, "model_dump", None)
    if dump is not None:
        return dump()
    return model.dict()


def _decode_cursor(cursor: str | None) -> int | None:
    if cursor is None:
        return None
    try:
        parsed = int(cursor)
    except ValueError:
        raise RuntimeConfigError("cursor is invalid") from None
    if parsed <= 0:
        raise RuntimeConfigError("cursor is invalid")
    return parsed


def _settings_schema(group: GroupChat) -> GroupSummarySettingsSchema:
    if group.summary_settings is None:
        return GroupSummarySettingsSchema(
            enabled=False,
            interval_minutes=_DEFAULT_INTERVAL_MINUTES,
            summary_profile_id=None,
            timezone=_DEFAULT_TIMEZONE,
        )
    return GroupSummarySettingsSchema(
        enabled=group.enabled,
        interval_minutes=group.interval_minutes or _DEFAULT_INTERVAL_MINUTES,
        summary_profile_id=group.summary_profile_id,
        timezone=group.timezone,
    )


def _effective_profile_schema(profile: SummaryProfile | None) -> EffectiveSummaryProfileSchema | None:
    if profile is None:
        return None
    provider = profile.llm_provider
    return EffectiveSummaryProfileSchema(
        id=profile.id,
        name=profile.name,
        model=profile.model or (provider.default_model if provider is not None else None),
        provider=provider.name if provider is not None else None,
    )


def _last_summary_schema(job: SummaryJob | None) -> GroupLastSummarySchema | None:
    if job is None:
        return None
    return GroupLastSummarySchema(
        status=job.status,
        finished_at=job.finished_at,
        error_type=job.error_type,
    )


def _delivery_schema(attempt) -> SummaryDeliverySchema | None:
    if attempt is None:
        return None
    return SummaryDeliverySchema(
        status=attempt.status,
        attempt_count=attempt.attempt_count,
        max_attempts=attempt.max_attempts,
        total_chunks=attempt.total_chunks,
        sent_chunks=attempt.sent_chunks,
        error_type=attempt.error_type,
        error_message=attempt.error_message,
        updated_at=attempt.updated_at,
    )


def _job_result_schema(
    result: SummaryJobResultView | None,
    *,
    delivery_by_result_id: dict[int, SummaryDeliverySchema] | None = None,
) -> SummaryJobResultSchema | None:
    if result is None:
        return None
    delivery_by_result_id = delivery_by_result_id or {}
    return SummaryJobResultSchema(
        id=result.id,
        prompt_version=result.prompt_version,
        llm_provider_id=result.llm_provider_id,
        summary_profile_id=result.summary_profile_id,
        model=result.model,
        interval_start_sequence=result.interval_start_sequence,
        interval_end_sequence=result.interval_end_sequence,
        created_at=result.created_at,
        delivery=delivery_by_result_id.get(result.id),
    )


def _sequence_range(starting_sequence: int, cutoff_sequence: int | None) -> str | None:
    if cutoff_sequence is None:
        return None
    return f"{starting_sequence + 1}-{cutoff_sequence}"


def _job_schema(
    job: SummaryJobView | None,
    *,
    provider_names: dict[int, str] | None = None,
    profile_names: dict[int, str] | None = None,
    delivery_by_result_id: dict[int, SummaryDeliverySchema] | None = None,
) -> SummaryJobSchema | None:
    if job is None:
        return None
    provider_names = provider_names or {}
    profile_names = profile_names or {}
    return SummaryJobSchema(
        id=job.id,
        group_id=job.group_id,
        chat_id=job.chat_id,
        trigger_type=job.trigger_type,
        status=job.status,
        sequence_range=_sequence_range(job.starting_sequence, job.cutoff_sequence),
        starting_sequence=job.starting_sequence,
        cutoff_sequence=job.cutoff_sequence,
        prompt_version=job.prompt_version,
        llm_provider_id=job.llm_provider_id,
        summary_profile_id=job.summary_profile_id,
        model=job.model,
        provider=provider_names.get(job.llm_provider_id) if job.llm_provider_id is not None else None,
        profile_name=profile_names.get(job.summary_profile_id) if job.summary_profile_id is not None else None,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_type=job.error_type,
        error_message=job.error_message,
        result=_job_result_schema(job.result, delivery_by_result_id=delivery_by_result_id),
    )


def _summary_test_task_schema(task: SummaryTestTaskView) -> SummaryTestTaskSchema:
    return SummaryTestTaskSchema(
        id=task.id,
        group_id=task.group_id,
        chat_id=task.chat_id,
        status=task.status,
        step=task.step,
        message_count=task.message_count,
        sequence_range=task.sequence_range,
        summary_text=task.summary_text,
        error_type=task.error_type,
        error_message=task.error_message,
        created_at=task.created_at,
        started_at=task.started_at,
        finished_at=task.finished_at,
    )


def _job_view_from_model(job: SummaryJob | None) -> SummaryJobView | None:
    if job is None:
        return None
    result = job.result
    return SummaryJobView(
        id=job.id,
        group_id=job.group_id,
        chat_id=job.chat_id,
        trigger_type=job.trigger_type,
        status=job.status,
        starting_sequence=job.starting_sequence,
        cutoff_sequence=job.cutoff_sequence,
        prompt_version=job.prompt_version,
        llm_provider_id=job.llm_provider_id,
        summary_profile_id=job.summary_profile_id,
        model=job.model,
        error_type=job.error_type,
        error_message=job.error_message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        result=(
            SummaryJobResultView(
                id=result.id,
                prompt_version=result.prompt_version,
                llm_provider_id=result.llm_provider_id,
                summary_profile_id=result.summary_profile_id,
                model=result.model,
                interval_start_sequence=result.interval_start_sequence,
                interval_end_sequence=result.interval_end_sequence,
                created_at=result.created_at,
            )
            if result is not None
            else None
        ),
    )


async def _effective_profile(session: AsyncSession, group: GroupChat) -> SummaryProfile | None:
    if group.summary_profile is not None:
        return group.summary_profile
    return await default_summary_profile(session)


async def _display_maps_for_jobs(
    session: AsyncSession,
    jobs: list[SummaryJobView],
) -> tuple[dict[int, str], dict[int, str]]:
    provider_ids = {job.llm_provider_id for job in jobs if job.llm_provider_id is not None}
    profile_ids = {job.summary_profile_id for job in jobs if job.summary_profile_id is not None}
    provider_names: dict[int, str] = {}
    profile_names: dict[int, str] = {}
    if provider_ids:
        rows = await session.execute(
            select(LLMProvider.id, LLMProvider.name).where(LLMProvider.id.in_(provider_ids))
        )
        provider_names = {provider_id: name for provider_id, name in rows}
    if profile_ids:
        rows = await session.execute(
            select(SummaryProfile.id, SummaryProfile.name).where(SummaryProfile.id.in_(profile_ids))
        )
        profile_names = {profile_id: name for profile_id, name in rows}
    return provider_names, profile_names


async def _delivery_map_for_jobs(
    session: AsyncSession,
    jobs: list[SummaryJobView],
) -> dict[int, SummaryDeliverySchema]:
    result_ids = [job.result.id for job in jobs if job.result is not None]
    deliveries: dict[int, SummaryDeliverySchema] = {}
    for result_id in result_ids:
        attempt = await latest_summary_delivery_attempt(session, summary_result_id=result_id)
        delivery = _delivery_schema(attempt)
        if delivery is not None:
            deliveries[result_id] = delivery
    return deliveries


async def _group_list_item_schema(session: AsyncSession, group: GroupChat) -> GroupListItemSchema:
    recent_jobs = await recent_summary_jobs_for_group(session, group_id=group.id, limit=1)
    return GroupListItemSchema(
        id=group.id,
        chat_id=group.chat_id,
        chat_type=group.chat_type,
        title=group.title,
        username=group.username,
        discovered_at=group.discovered_at,
        settings=_settings_schema(group),
        effective_profile=_effective_profile_schema(await _effective_profile(session, group)),
        last_summary=_last_summary_schema(recent_jobs[0] if recent_jobs else None),
    )


async def _get_group(session: AsyncSession, group_id: int) -> GroupChat | None:
    return await session.get(
        GroupChat,
        group_id,
        options=[
            selectinload(GroupChat.summary_profile).selectinload(SummaryProfile.llm_provider),
            selectinload(GroupChat.summary_state),
        ],
    )


def _groups_statement_with_filters(
    *,
    q: str | None,
    enabled: bool | None,
    profile_id: int | None,
    status: str | None,
    cursor_id: int | None,
):
    statement = (
        select(GroupChat)
        .options(
            selectinload(GroupChat.summary_profile).selectinload(SummaryProfile.llm_provider),
            selectinload(GroupChat.summary_state),
        )
        .order_by(GroupChat.id)
    )
    if cursor_id is not None:
        statement = statement.where(GroupChat.id > cursor_id)
    if q is not None and q.strip():
        statement = statement.where(GroupChat.title.ilike(f"%{q.strip()}%"))
    if enabled is not None:
        statement = statement.where(GroupChat.enabled.is_(enabled))
    if profile_id is not None:
        statement = statement.where(GroupChat.summary_profile_id == profile_id)
    if status is not None:
        latest_job_ids = (
            select(
                SummaryJob.group_id.label("group_id"),
                func.max(SummaryJob.id).label("job_id"),
            )
            .group_by(SummaryJob.group_id)
            .subquery()
        )
        latest_jobs = (
            select(
                SummaryJob.group_id.label("group_id"),
                SummaryJob.status.label("status"),
            )
            .join(latest_job_ids, SummaryJob.id == latest_job_ids.c.job_id)
            .subquery()
        )
        statement = statement.outerjoin(latest_jobs, latest_jobs.c.group_id == GroupChat.id)
        if status == "none":
            statement = statement.where(latest_jobs.c.group_id.is_(None))
        else:
            statement = statement.where(latest_jobs.c.status == status)
    return statement


@router.get("", response_model=GroupListResponse)
async def get_groups(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    q: Annotated[str | None, Query()] = None,
    enabled: Annotated[bool | None, Query()] = None,
    profile_id: Annotated[int | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query()] = 50,
    cursor: Annotated[str | None, Query()] = None,
) -> GroupListResponse | JSONResponse:
    try:
        normalized_limit = _normalize_limit(limit)
        cursor_id = _decode_cursor(cursor)
        if status is not None and status not in {*_SUMMARY_JOB_STATUSES, "none"}:
            raise RuntimeConfigError("status is not supported")

        async with session_factory() as session:
            statement = _groups_statement_with_filters(
                q=q,
                enabled=enabled,
                profile_id=profile_id,
                status=status,
                cursor_id=cursor_id,
            )
            groups = (await session.scalars(statement.limit(normalized_limit + 1))).unique().all()
            has_more = len(groups) > normalized_limit
            groups = groups[:normalized_limit]
            items = [await _group_list_item_schema(session, group) for group in groups]
            next_cursor = str(groups[-1].id) if has_more and groups else None
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )
    return GroupListResponse(items=items, next_cursor=next_cursor)


@router.post("/refresh-userbot", response_model=GroupDiscoveryRefreshResponse)
async def refresh_userbot_groups(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    discovery_provider: Annotated[
        DialogDiscoveryProvider | None,
        Depends(get_userbot_dialog_discovery_provider),
    ],
) -> GroupDiscoveryRefreshResponse | JSONResponse:
    if discovery_provider is None:
        return api_error_response(
            status_code=409,
            code="conflict",
            message="userbot dialog discovery is unavailable",
        )
    try:
        async with session_scope(session_factory) as session:
            result = await refresh_enabled_userbot_dialogs(
                session,
                secret_service=secret_service,
                discover_dialogs=discovery_provider,
            )
    except UserbotConfigError as exc:
        return api_error_response(
            status_code=409,
            code="conflict",
            message=str(exc),
        )
    return GroupDiscoveryRefreshResponse(
        discovered=result.discovered,
        created=result.created,
        updated=result.updated,
        ignored=result.ignored,
    )


@router.get("/{group_id}", response_model=GroupDetailSchema)
async def get_group(
    group_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> GroupDetailSchema | JSONResponse:
    async with session_factory() as session:
        group = await _get_group(session, group_id)
        if group is None:
            return api_error_response(
                status_code=404,
                code="not_found",
                message="group not found",
            )
        item = await _group_list_item_schema(session, group)
        active_job = await get_active_summary_job(session, group_id=group.id)
        recent_jobs = await recent_summary_jobs_for_group(session, group_id=group.id, limit=10)
        job_views = [
            job_view
            for job in [active_job, *recent_jobs]
            if (job_view := _job_view_from_model(job)) is not None
        ]
        provider_names, profile_names = await _display_maps_for_jobs(session, job_views)
        delivery_by_result_id = await _delivery_map_for_jobs(session, job_views)
        state = group.summary_state
        return GroupDetailSchema(
            **_model_data(item),
            summary_state=(
                GroupSummaryStateSchema(
                    last_summary_sequence=state.last_summary_sequence,
                    last_summary_at=state.last_summary_at,
                )
                if state is not None
                else None
            ),
            active_job=_job_schema(
                _job_view_from_model(active_job),
                provider_names=provider_names,
                profile_names=profile_names,
                delivery_by_result_id=delivery_by_result_id,
            ),
            recent_jobs=[
                job_schema
                for job in recent_jobs
                if (
                    job_schema := _job_schema(
                        _job_view_from_model(job),
                        provider_names=provider_names,
                        profile_names=profile_names,
                        delivery_by_result_id=delivery_by_result_id,
                    )
                )
                is not None
            ],
        )


@router.patch("/{group_id}/summary-settings", response_model=GroupDetailSchema)
async def patch_group_summary_settings(
    group_id: int,
    payload: GroupSummarySettingsUpdateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    actor: Annotated[str, Depends(get_actor)],
) -> GroupDetailSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            group = await _get_group(session, group_id)
            if group is None:
                return api_error_response(
                    status_code=404,
                    code="not_found",
                    message="group not found",
                )
            profile = None
            if payload.summary_profile_id is not None:
                profile = await get_summary_profile(session, payload.summary_profile_id)
            settings = await set_group_summary_settings(
                session,
                group=group,
                enabled=payload.enabled,
                interval_minutes=payload.interval_minutes,
                summary_profile=profile,
                timezone=payload.timezone,
                actor=actor,
            )
            await session.refresh(group)
            group = await _get_group(session, group_id)
            if group is None:
                raise RuntimeError("updated group unexpectedly missing")
            item = await _group_list_item_schema(session, group)
            active_job = await get_active_summary_job(session, group_id=group.id)
            recent_jobs = await recent_summary_jobs_for_group(session, group_id=group.id, limit=10)
            provider_names, profile_names = await _display_maps_for_jobs(
                session,
                job_views := [
                    job_view
                    for job in [active_job, *recent_jobs]
                    if (job_view := _job_view_from_model(job)) is not None
                ],
            )
            delivery_by_result_id = await _delivery_map_for_jobs(session, job_views)
            state = group.summary_state
    except SummaryProfileNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary profile not found",
        )
    except RuntimeConfigError as exc:
        message = str(exc)
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=message,
        )
    return GroupDetailSchema(
        **_model_data(item),
        summary_state=(
            GroupSummaryStateSchema(
                last_summary_sequence=state.last_summary_sequence,
                last_summary_at=state.last_summary_at,
            )
            if state is not None
            else None
        ),
        active_job=_job_schema(
            _job_view_from_model(active_job),
            provider_names=provider_names,
            profile_names=profile_names,
            delivery_by_result_id=delivery_by_result_id,
        ),
        recent_jobs=[
            job_schema
            for job in recent_jobs
            if (
                job_schema := _job_schema(
                    _job_view_from_model(job),
                    provider_names=provider_names,
                    profile_names=profile_names,
                    delivery_by_result_id=delivery_by_result_id,
                )
            )
            is not None
        ],
    )


@router.post("/{group_id}/summary-test-tasks", response_model=TriggerSummaryTestTaskResponse, status_code=202)
async def post_group_summary_test_task(
    group_id: int,
    response: Response,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    registry: Annotated[SummaryTestTaskRegistry, Depends(get_summary_test_task_registry)],
) -> TriggerSummaryTestTaskResponse | JSONResponse:
    async with session_factory() as session:
        group = await _get_group(session, group_id)
        if group is None:
            return api_error_response(
                status_code=404,
                code="not_found",
                message="group not found",
            )
        scheduled_group_id = group.id
        scheduled_chat_id = group.chat_id

    try:
        task = await registry.create_task(
            session_factory=session_factory,
            secret_service=secret_service,
            group_id=scheduled_group_id,
            chat_id=scheduled_chat_id,
        )
    except SummaryTestTaskRegistryFullError:
        return api_error_response(
            status_code=409,
            code="summary_test_task_busy",
            message="测试摘要任务已满，请稍后重试",
        )

    poll_url = f"/api/groups/{group_id}/summary-test-tasks/{task.id}"
    response.status_code = 202
    return TriggerSummaryTestTaskResponse(task=_summary_test_task_schema(task), poll_url=poll_url)


@router.get("/{group_id}/summary-test-tasks/{task_id}", response_model=SummaryTestTaskSchema)
async def get_group_summary_test_task(
    group_id: int,
    task_id: str,
    registry: Annotated[SummaryTestTaskRegistry, Depends(get_summary_test_task_registry)],
) -> SummaryTestTaskSchema | JSONResponse:
    task = await registry.get_task(task_id)
    if task is None or task.group_id != group_id:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary test task not found",
        )
    return _summary_test_task_schema(task)


@router.post("/{group_id}/summary-test-tasks/{task_id}/cancel", response_model=SummaryTestTaskSchema)
async def post_group_summary_test_task_cancel(
    group_id: int,
    task_id: str,
    registry: Annotated[SummaryTestTaskRegistry, Depends(get_summary_test_task_registry)],
) -> SummaryTestTaskSchema | JSONResponse:
    task = await registry.cancel_task(task_id)
    if task is None or task.group_id != group_id:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary test task not found",
        )
    return _summary_test_task_schema(task)


@router.post("/{group_id}/summary-jobs", response_model=TriggerSummaryJobResponse, status_code=202)
async def post_group_summary_job(
    group_id: int,
    response: Response,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
    notification_dispatcher: Annotated[
        SummaryNotificationDispatcher | None,
        Depends(get_summary_notification_dispatcher),
    ],
) -> TriggerSummaryJobResponse | JSONResponse:
    scheduled_group_id: int | None = None
    scheduled_job_id: int | None = None
    try:
        async with session_scope(session_factory) as session:
            group = await _get_group(session, group_id)
            if group is None:
                return api_error_response(
                    status_code=404,
                    code="not_found",
                    message="group not found",
                )
            job = await create_manual_summary_job(session, group=group)
            await create_audit_log(
                session,
                actor=actor,
                action="trigger_summary",
                entity_type="summary_job",
                entity_id=str(job.id),
                redacted_after={
                    "group_id": group.id,
                    "chat_id": group.chat_id,
                    "job_id": job.id,
                    "trigger_type": "manual",
                    "status": job.status,
                },
            )
            scheduled_group_id = group.id
            scheduled_job_id = job.id
    except SummaryJobConflictError as exc:
        return api_error_response(
            status_code=409,
            code="summary_job_conflict",
            message="该群有摘要正在生成",
            details={"active_job_id": exc.active_job_id},
        )
    if scheduled_group_id is None or scheduled_job_id is None:
        raise RuntimeError("created summary job unexpectedly missing")
    schedule_manual_summary_job(
        session_factory=session_factory,
        secret_service=secret_service,
        group_id=scheduled_group_id,
        job_id=scheduled_job_id,
        schedule_notification=(
            notification_dispatcher.schedule if notification_dispatcher is not None else None
        ),
    )
    poll_url = f"/api/groups/{group_id}/summary-jobs/{job.id}"
    response.status_code = 202
    async with session_factory() as session:
        provider_names, profile_names = await _display_maps_for_jobs(session, [job])
    job_schema = _job_schema(job, provider_names=provider_names, profile_names=profile_names)
    if job_schema is None:
        raise RuntimeError("created summary job unexpectedly missing")
    return TriggerSummaryJobResponse(job=job_schema, poll_url=poll_url)


@router.get("/{group_id}/summary-jobs/{job_id}", response_model=SummaryJobSchema)
async def get_group_summary_job(
    group_id: int,
    job_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> SummaryJobSchema | JSONResponse:
    async with session_factory() as session:
        group = await _get_group(session, group_id)
        if group is None:
            return api_error_response(
                status_code=404,
                code="not_found",
                message="group not found",
            )
        try:
            job = await get_summary_job_status(session, group=group, job_id=job_id)
        except SummaryJobNotFoundError:
            return api_error_response(
                status_code=404,
                code="not_found",
                message="summary job not found",
            )
        provider_names, profile_names = await _display_maps_for_jobs(session, [job])
        delivery_by_result_id = await _delivery_map_for_jobs(session, [job])
        job_schema = _job_schema(
            job,
            provider_names=provider_names,
            profile_names=profile_names,
            delivery_by_result_id=delivery_by_result_id,
        )
    if job_schema is None:
        raise RuntimeError("summary job unexpectedly missing")
    return job_schema
