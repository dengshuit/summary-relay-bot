from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.userbot_auth import (
    SummaryUserbotView,
    UserbotAuthFlowError,
    UserbotConfigError,
    UserbotNotFoundError,
    create_summary_userbot,
    list_current_userbot,
    request_userbot_phone_code,
    sign_in_summary_userbot,
    summary_userbot_view,
    submit_summary_userbot_password,
    update_summary_userbot,
)
from summary_relay_bot.telegram.userbot import UserbotClientFactory, create_telethon_userbot_client
from summary_relay_bot.web.deps import (
    get_actor,
    get_secret_service,
    get_session_factory,
    get_userbot_client_factory,
)
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    SecretStateSchema,
    UserbotCreateRequest,
    UserbotResponse,
    UserbotSchema,
    UserbotSecretsSchema,
    UserbotSendCodeRequest,
    UserbotSignInRequest,
    UserbotSubmitPasswordRequest,
    UserbotUpdateRequest,
)


router = APIRouter(prefix="/userbot", tags=["userbot"])


def _provided_fields(model: BaseModel) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields)


def _client_factory(factory: UserbotClientFactory | None) -> UserbotClientFactory:
    return factory or create_telethon_userbot_client


def _secret_schema(secret) -> SecretStateSchema:
    return SecretStateSchema(
        configured=secret.configured,
        updated_at=secret.updated_at,
    )


def _userbot_schema(userbot: SummaryUserbotView | None) -> UserbotSchema | None:
    if userbot is None:
        return None
    return UserbotSchema(
        id=userbot.id,
        name=userbot.name,
        api_id=userbot.api_id,
        phone_number_redacted=userbot.phone_number_redacted,
        enabled=userbot.enabled,
        auth_status=userbot.auth_status,
        runtime_status=userbot.runtime_status,
        telegram_user_id=userbot.telegram_user_id,
        telegram_username=userbot.telegram_username,
        telegram_display_name=userbot.telegram_display_name,
        last_authorized_at=userbot.last_authorized_at,
        last_started_at=userbot.last_started_at,
        last_stopped_at=userbot.last_stopped_at,
        last_error_type=userbot.last_error_type,
        last_error_message=userbot.last_error_message,
        created_at=userbot.created_at,
        updated_at=userbot.updated_at,
        secrets=UserbotSecretsSchema(
            api_hash=_secret_schema(userbot.secrets.api_hash),
            phone_number=_secret_schema(userbot.secrets.phone_number),
            session=_secret_schema(userbot.secrets.session),
            proxy_url=_secret_schema(userbot.secrets.proxy_url),
        ),
    )


def _response(active: SummaryUserbotView | None, item: SummaryUserbotView | None) -> UserbotResponse:
    return UserbotResponse(
        active=active.id if active is not None else None,
        item=_userbot_schema(item),
    )


def _validation_error(exc: Exception) -> JSONResponse:
    return api_error_response(
        status_code=400,
        code="validation_error",
        message=str(exc),
    )


@router.get("", response_model=UserbotResponse)
async def get_userbot(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> UserbotResponse:
    async with session_factory() as session:
        active, item = await list_current_userbot(session)
    return _response(active, item)


@router.post("", response_model=UserbotSchema)
async def post_userbot(
    payload: UserbotCreateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
) -> UserbotSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            userbot = await create_summary_userbot(
                session,
                secret_service=secret_service,
                name=payload.name,
                api_id=payload.api_id,
                api_hash=payload.api_hash,
                phone_number=payload.phone_number,
                proxy_url=payload.proxy_url,
                enabled=payload.enabled,
                actor=actor,
            )
            schema = _userbot_schema(summary_userbot_view(userbot))
            if schema is None:
                raise RuntimeError("created userbot unexpectedly missing")
            return schema
    except UserbotConfigError as exc:
        return _validation_error(exc)


@router.patch("", response_model=UserbotSchema)
async def patch_userbot(
    payload: UserbotUpdateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
) -> UserbotSchema | JSONResponse:
    fields = _provided_fields(payload)
    update_fields = {
        name: getattr(payload, name)
        for name in (
            "name",
            "api_id",
            "api_hash",
            "phone_number",
            "proxy_url",
            "enabled",
        )
        if name in fields
    }
    try:
        async with session_scope(session_factory) as session:
            userbot = await update_summary_userbot(
                session,
                secret_service=secret_service,
                userbot_id=payload.id,
                actor=actor,
                **update_fields,
            )
    except UserbotNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary userbot not found",
        )
    except UserbotConfigError as exc:
        return _validation_error(exc)
    schema = _userbot_schema(userbot)
    if schema is None:
        raise RuntimeError("updated userbot unexpectedly missing")
    return schema


@router.post("/send-code", response_model=UserbotSchema)
async def send_userbot_code(
    payload: UserbotSendCodeRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
    injected_client_factory: Annotated[UserbotClientFactory | None, Depends(get_userbot_client_factory)],
) -> UserbotSchema | JSONResponse:
    fields = _provided_fields(payload)
    update_fields = {
        name: getattr(payload, name)
        for name in ("api_id", "api_hash", "phone_number", "proxy_url")
        if name in fields
    }
    try:
        async with session_scope(session_factory) as session:
            userbot = await request_userbot_phone_code(
                session,
                secret_service=secret_service,
                client_factory=_client_factory(injected_client_factory),
                userbot_id=payload.id,
                actor=actor,
                **update_fields,
            )
    except UserbotNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary userbot not found",
        )
    except (UserbotConfigError, UserbotAuthFlowError) as exc:
        return _validation_error(exc)
    schema = _userbot_schema(userbot)
    if schema is None:
        raise RuntimeError("userbot unexpectedly missing after code request")
    return schema


@router.post("/sign-in", response_model=UserbotSchema)
async def sign_in_userbot(
    payload: UserbotSignInRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
    injected_client_factory: Annotated[UserbotClientFactory | None, Depends(get_userbot_client_factory)],
) -> UserbotSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            userbot = await sign_in_summary_userbot(
                session,
                secret_service=secret_service,
                client_factory=_client_factory(injected_client_factory),
                userbot_id=payload.id,
                code=payload.code,
                actor=actor,
            )
    except UserbotNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary userbot not found",
        )
    except (UserbotConfigError, UserbotAuthFlowError) as exc:
        return _validation_error(exc)
    schema = _userbot_schema(userbot)
    if schema is None:
        raise RuntimeError("userbot unexpectedly missing after sign-in")
    return schema


@router.post("/submit-password", response_model=UserbotSchema)
async def submit_userbot_password(
    payload: UserbotSubmitPasswordRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
    injected_client_factory: Annotated[UserbotClientFactory | None, Depends(get_userbot_client_factory)],
) -> UserbotSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            userbot = await submit_summary_userbot_password(
                session,
                secret_service=secret_service,
                client_factory=_client_factory(injected_client_factory),
                userbot_id=payload.id,
                password=payload.password,
                actor=actor,
            )
    except UserbotNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary userbot not found",
        )
    except (UserbotConfigError, UserbotAuthFlowError) as exc:
        return _validation_error(exc)
    schema = _userbot_schema(userbot)
    if schema is None:
        raise RuntimeError("userbot unexpectedly missing after password submission")
    return schema
