from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    BotInstanceNotFoundError,
    BotInstanceView,
    BotValidationResult,
    RuntimeConfigError,
    SecretState,
    create_bot_instance,
    list_bot_instances,
    redact_owner_id,
    update_bot_instance,
    validate_bot_instance,
)
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.telegram_runtime import RuntimeBusyError, TelegramRuntimeManager
from summary_relay_bot.web.deps import (
    get_actor,
    get_secret_service,
    get_session_factory,
    get_telegram_runtime,
)
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    BotCreateRequest,
    BotInstanceSchema,
    BotListResponse,
    BotUpdateRequest,
    BotValidateRequest,
    BotValidateResponse,
    SecretStateSchema,
)


router = APIRouter(prefix="/bot", tags=["bot"])


def _provided_fields(model: BaseModel) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields)


def _bot_schema(bot: BotInstanceView | None) -> BotInstanceSchema | None:
    if bot is None:
        return None
    return BotInstanceSchema(
        id=bot.id,
        name=bot.name,
        owner_id_redacted=bot.owner_id_redacted,
        telegram_bot_id=bot.telegram_bot_id,
        telegram_username=bot.telegram_username,
        enabled=bot.enabled,
        status=bot.status,
        needs_restart=bot.needs_restart,
        last_validated_at=bot.last_validated_at,
        secret=SecretStateSchema(
            configured=bot.secret.configured,
            updated_at=bot.secret.updated_at,
        ),
    )


def _validation_schema(result: BotValidationResult) -> BotValidateResponse:
    success = result.status == "valid"
    return BotValidateResponse(
        success=success,
        detail="Bot token validated successfully" if success else (result.error_message or "Bot validation failed"),
        status=result.status,
        last_validated_at=result.last_validated_at,
        bot_id=result.telegram_bot_id,
        username=result.telegram_username,
        error_type=result.error_type,
        error_message=result.error_message,
    )


def _runtime_busy_response() -> JSONResponse:
    return api_error_response(
        status_code=409,
        code="runtime_busy",
        message="Bot runtime reload is blocked by an active summary; retry after it finishes",
    )


def _has_non_empty_secret(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _patch_requires_runtime_reload(payload: BotUpdateRequest, fields: set[str]) -> bool:
    return (
        ("owner_id" in fields and payload.owner_id is not None)
        or ("enabled" in fields and payload.enabled is not None)
        or ("bot_token" in fields and _has_non_empty_secret(payload.bot_token))
    )


@router.get("", response_model=BotListResponse)
async def get_bot_config(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> BotListResponse:
    async with session_factory() as session:
        active, items = await list_bot_instances(session)
    return BotListResponse(
        active=active.id if active is not None else None,
        items=[schema for item in items if (schema := _bot_schema(item)) is not None],
    )


@router.post("", response_model=BotInstanceSchema)
async def post_bot_config(
    payload: BotCreateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
    telegram_runtime: Annotated[TelegramRuntimeManager | None, Depends(get_telegram_runtime)],
) -> BotInstanceSchema | JSONResponse:
    try:
        if payload.enabled and telegram_runtime is not None:
            bot = await telegram_runtime.reload_after_change(
                lambda session: _create_bot_instance_view(
                    session,
                    secret_service=secret_service,
                    payload=payload,
                    actor=actor,
                )
            )
            schema = _bot_schema(bot)
            if schema is None:
                raise RuntimeError("created bot instance unexpectedly missing")
            return schema
        async with session_scope(session_factory) as session:
            bot = await create_bot_instance(
                session,
                secret_service=secret_service,
                name=payload.name,
                bot_token=payload.bot_token,
                owner_id=payload.owner_id,
                enabled=payload.enabled,
                actor=actor,
            )
            schema = _bot_schema(
                BotInstanceView(
                    id=bot.id,
                    name=bot.name,
                    owner_id_redacted=redact_owner_id(bot.owner_id) or "",
                    telegram_bot_id=bot.telegram_bot_id,
                    telegram_username=bot.telegram_username,
                    enabled=bot.enabled,
                    status=bot.status,
                    needs_restart=bot.needs_restart,
                    last_validated_at=bot.last_validated_at,
                    secret=SecretState(configured=bool(bot.bot_token_encrypted), updated_at=None),
                )
            )
            if schema is None:
                raise RuntimeError("created bot instance unexpectedly missing")
            return schema
    except RuntimeBusyError:
        return _runtime_busy_response()
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )


@router.post("/validate", response_model=BotValidateResponse)
async def validate_bot_config(
    payload: BotValidateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
) -> BotValidateResponse | JSONResponse:
    fields = _provided_fields(payload)
    validate_fields = {}
    if "bot_token" in fields:
        validate_fields["bot_token"] = payload.bot_token
    try:
        async with session_scope(session_factory) as session:
            result = await validate_bot_instance(
                session,
                secret_service=secret_service,
                bot_instance_id=payload.id,
                **validate_fields,
            )
    except BotInstanceNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="bot instance not found",
        )
    return _validation_schema(result)


@router.patch("", response_model=BotInstanceSchema)
async def patch_bot_config(
    payload: BotUpdateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
    telegram_runtime: Annotated[TelegramRuntimeManager | None, Depends(get_telegram_runtime)],
) -> BotInstanceSchema | JSONResponse:
    fields = _provided_fields(payload)
    update_fields = {
        name: getattr(payload, name)
        for name in ("name", "owner_id", "enabled", "bot_token")
        if name in fields
    }
    try:
        if telegram_runtime is not None and _patch_requires_runtime_reload(payload, fields):
            bot = await telegram_runtime.reload_after_change(
                lambda session: update_bot_instance(
                    session,
                    secret_service=secret_service,
                    bot_instance_id=payload.id,
                    actor=actor,
                    **update_fields,
                )
            )
        else:
            async with session_scope(session_factory) as session:
                bot = await update_bot_instance(
                    session,
                    secret_service=secret_service,
                    bot_instance_id=payload.id,
                    actor=actor,
                    **update_fields,
                )
    except BotInstanceNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="bot instance not found",
        )
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )
    except RuntimeBusyError:
        return _runtime_busy_response()
    schema = _bot_schema(bot)
    if schema is None:
        raise RuntimeError("updated bot instance unexpectedly missing")
    return schema


async def _create_bot_instance_view(
    session: AsyncSession,
    *,
    secret_service: SecretService,
    payload: BotCreateRequest,
    actor: str,
) -> BotInstanceView:
    bot = await create_bot_instance(
        session,
        secret_service=secret_service,
        name=payload.name,
        bot_token=payload.bot_token,
        owner_id=payload.owner_id,
        enabled=payload.enabled,
        actor=actor,
    )
    return BotInstanceView(
        id=bot.id,
        name=bot.name,
        owner_id_redacted=redact_owner_id(bot.owner_id) or "",
        telegram_bot_id=bot.telegram_bot_id,
        telegram_username=bot.telegram_username,
        enabled=bot.enabled,
        status=bot.status,
        needs_restart=bot.needs_restart,
        last_validated_at=bot.last_validated_at,
        secret=SecretState(configured=bool(bot.bot_token_encrypted), updated_at=None),
    )
