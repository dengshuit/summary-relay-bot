from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    LLMProviderNotFoundError,
    LLMProviderValidationResult,
    LLMProviderView,
    RuntimeConfigError,
    SecretState,
    create_llm_provider,
    list_llm_providers,
    update_llm_provider,
    validate_llm_provider,
)
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.deps import get_actor, get_secret_service, get_session_factory
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    LLMProviderCreateRequest,
    LLMProviderListResponse,
    LLMProviderSchema,
    LLMProviderTestResponse,
    LLMProviderUpdateRequest,
    SecretStateSchema,
)


router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])


def _provided_fields(model: BaseModel) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields)


def _provider_schema(provider: LLMProviderView) -> LLMProviderSchema:
    return LLMProviderSchema(
        id=provider.id,
        name=provider.name,
        provider_type=provider.provider_type,
        base_url=provider.base_url,
        default_model=provider.default_model,
        timeout_seconds=provider.timeout_seconds,
        max_retries=provider.max_retries,
        enabled=provider.enabled,
        status=provider.status,
        last_validated_at=provider.last_validated_at,
        secret=SecretStateSchema(
            configured=provider.secret.configured,
            updated_at=provider.secret.updated_at,
        ),
    )


def _validation_schema(result: LLMProviderValidationResult) -> LLMProviderTestResponse:
    return LLMProviderTestResponse(
        status=result.status,
        last_validated_at=result.last_validated_at,
        error_type=result.error_type,
        error_message=result.error_message,
    )


@router.get("", response_model=LLMProviderListResponse)
async def get_llm_providers(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    enabled: Annotated[bool | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> LLMProviderListResponse | JSONResponse:
    try:
        async with session_factory() as session:
            providers = await list_llm_providers(session, enabled=enabled, status=status)
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )
    return LLMProviderListResponse(items=[_provider_schema(provider) for provider in providers])


@router.post("", response_model=LLMProviderSchema)
async def post_llm_provider(
    payload: LLMProviderCreateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
) -> LLMProviderSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            provider = await create_llm_provider(
                session,
                secret_service=secret_service,
                name=payload.name,
                provider_type=payload.provider_type,
                base_url=payload.base_url,
                api_key=payload.api_key,
                default_model=payload.default_model,
                timeout_seconds=payload.timeout_seconds,
                max_retries=payload.max_retries,
                enabled=payload.enabled,
                actor=actor,
            )
            return _provider_schema(LLMProviderView(
                id=provider.id,
                name=provider.name,
                provider_type=provider.provider_type,
                base_url=provider.base_url,
                default_model=provider.default_model,
                timeout_seconds=provider.timeout_seconds,
                max_retries=provider.max_retries,
                enabled=provider.enabled,
                status=provider.status,
                last_validated_at=provider.last_validated_at,
                secret=SecretState(configured=bool(provider.api_key_encrypted), updated_at=None),
            ))
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )


@router.patch("/{provider_id}", response_model=LLMProviderSchema)
async def patch_llm_provider(
    provider_id: int,
    payload: LLMProviderUpdateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
    actor: Annotated[str, Depends(get_actor)],
) -> LLMProviderSchema | JSONResponse:
    fields = _provided_fields(payload)
    update_fields = {
        name: getattr(payload, name)
        for name in (
            "name",
            "provider_type",
            "base_url",
            "api_key",
            "default_model",
            "timeout_seconds",
            "max_retries",
            "enabled",
        )
        if name in fields
    }
    try:
        async with session_scope(session_factory) as session:
            provider = await update_llm_provider(
                session,
                secret_service=secret_service,
                provider_id=provider_id,
                actor=actor,
                **update_fields,
            )
    except LLMProviderNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="llm provider not found",
        )
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )
    return _provider_schema(provider)


@router.post("/{provider_id}/test", response_model=LLMProviderTestResponse)
async def test_llm_provider(
    provider_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    secret_service: Annotated[SecretService, Depends(get_secret_service)],
) -> LLMProviderTestResponse | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            result = await validate_llm_provider(
                session,
                secret_service=secret_service,
                provider_id=provider_id,
            )
    except LLMProviderNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="llm provider not found",
        )
    return _validation_schema(result)
