from __future__ import annotations

from typing import Annotated, Any

import httpx
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    LLMProviderNotFoundError,
    LLMProviderInUseError,
    LLMProviderValidationResult,
    LLMProviderView,
    RuntimeConfigError,
    SecretState,
    create_llm_provider,
    delete_llm_provider,
    get_llm_provider,
    list_llm_providers,
    update_llm_provider,
    validate_llm_provider,
)
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.deps import get_actor, get_secret_service, get_session_factory
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    DeleteResponse,
    FetchProviderModelsRequest,
    FetchProviderModelsResponse,
    LLMProviderCreateRequest,
    LLMProviderSchema,
    LLMProviderTestResponse,
    LLMProviderUpdateRequest,
    ProviderModelsResponse,
    SecretStateSchema,
)


router = APIRouter(prefix="/llm-providers", tags=["llm-providers"])

_OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
_ANTHROPIC_MODEL_PRESETS = [
    "claude-3-5-sonnet-latest",
    "claude-3-5-haiku-latest",
    "claude-3-opus-20240229",
    "claude-3-sonnet-20240229",
]


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
        models=provider.models,
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
    success = result.status == "valid"
    return LLMProviderTestResponse(
        success=success,
        detail="LLM provider connection validated successfully"
        if success
        else (result.error_message or "LLM provider validation failed"),
        status=result.status,
        last_validated_at=result.last_validated_at,
        error_type=result.error_type,
        error_message=result.error_message,
    )


def _extract_openai_models(data: Any) -> list[str]:
    if not isinstance(data, dict):
        return []
    items = data.get("data")
    if not isinstance(items, list):
        return []
    models: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        model_id = item.get("id")
        if isinstance(model_id, str) and model_id.strip():
            models.append(model_id.strip())
    return sorted(dict.fromkeys(models))


async def _fetch_openai_models(
    *,
    provider_type: str,
    base_url: str | None,
    api_key: str | None,
) -> list[str]:
    if provider_type == "openai_compatible" and not base_url:
        raise RuntimeConfigError("base_url is required for openai_compatible provider")
    if not api_key or api_key.strip() == "":
        raise RuntimeConfigError("api_key is required to fetch upstream models")

    root = (base_url or _OPENAI_DEFAULT_BASE_URL).rstrip("/")
    endpoint = f"{root}/models"
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(endpoint, headers={"Authorization": f"Bearer {api_key.strip()}"})
        response.raise_for_status()
    return _extract_openai_models(response.json())


@router.get("", response_model=list[LLMProviderSchema])
async def get_llm_providers(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    enabled: Annotated[bool | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> list[LLMProviderSchema] | JSONResponse:
    try:
        async with session_factory() as session:
            providers = await list_llm_providers(session, enabled=enabled, status=status)
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )
    return [_provider_schema(provider) for provider in providers]


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
                models=payload.models,
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
                models=provider.models,
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
            "models",
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


@router.delete("/{provider_id}", response_model=DeleteResponse)
async def delete_provider(
    provider_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    actor: Annotated[str, Depends(get_actor)],
) -> DeleteResponse | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            await delete_llm_provider(session, provider_id=provider_id, actor=actor)
    except LLMProviderNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="llm provider not found",
        )
    except LLMProviderInUseError as exc:
        return api_error_response(
            status_code=409,
            code="conflict",
            message=str(exc),
        )
    return DeleteResponse(success=True)


@router.get("/{provider_id}/models", response_model=ProviderModelsResponse)
async def get_provider_models(
    provider_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> ProviderModelsResponse | JSONResponse:
    try:
        async with session_factory() as session:
            provider = await get_llm_provider(session, provider_id)
            models = provider.models if provider.models else [provider.default_model]
    except LLMProviderNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="llm provider not found",
        )
    return ProviderModelsResponse(success=True, models=models)


@router.post("/fetch-models", response_model=FetchProviderModelsResponse)
async def fetch_provider_models(
    payload: FetchProviderModelsRequest,
) -> FetchProviderModelsResponse | JSONResponse:
    try:
        if payload.provider_type == "anthropic":
            return FetchProviderModelsResponse(
                success=True,
                source="preset",
                detail="Anthropic model presets returned",
                models=_ANTHROPIC_MODEL_PRESETS,
            )
        if payload.provider_type not in {"openai", "openai_compatible"}:
            raise RuntimeConfigError("provider_type is not supported")
        models = await _fetch_openai_models(
            provider_type=payload.provider_type,
            base_url=payload.base_url,
            api_key=payload.api_key,
        )
    except RuntimeConfigError as exc:
        return api_error_response(
            status_code=400,
            code="validation_error",
            message=str(exc),
        )
    except httpx.HTTPError:
        return api_error_response(
            status_code=400,
            code="upstream_error",
            message="upstream model fetch failed",
        )
    return FetchProviderModelsResponse(
        success=True,
        source="upstream",
        detail="Upstream models fetched successfully",
        models=models,
    )


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
