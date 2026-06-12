from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import (
    LLMProviderNotFoundError,
    RuntimeConfigError,
    SummaryProfileInUseError,
    SummaryProfileNotFoundError,
    SummaryProfileProviderView,
    SummaryProfileView,
    create_summary_profile,
    delete_summary_profile,
    get_llm_provider,
    list_summary_profiles,
    set_default_summary_profile,
    update_summary_profile,
)
from summary_relay_bot.web.deps import get_actor, get_session_factory
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import (
    DeleteResponse,
    SummaryProfileCreateRequest,
    SummaryProfileSchema,
    SummaryProfileUpdateRequest,
)


router = APIRouter(prefix="/summary-profiles", tags=["summary-profiles"])


def _provided_fields(model: BaseModel) -> set[str]:
    fields = getattr(model, "model_fields_set", None)
    if fields is None:
        fields = getattr(model, "__fields_set__", set())
    return set(fields)


def _profile_schema(profile: SummaryProfileView) -> SummaryProfileSchema:
    return SummaryProfileSchema(
        id=profile.id,
        name=profile.name,
        llm_provider_id=profile.llm_provider.id,
        llm_provider_name=profile.llm_provider.name,
        provider_type=profile.llm_provider.provider_type,
        model=profile.model,
        effective_model=profile.effective_model,
        uses_provider_default_model=profile.uses_provider_default_model,
        prompt_version=profile.prompt_version,
        system_prompt=profile.system_prompt,
        temperature=profile.temperature,
        max_output_tokens=profile.max_output_tokens,
        enabled=profile.enabled,
        is_default=profile.is_default,
    )


@router.get("", response_model=list[SummaryProfileSchema])
async def get_summary_profiles(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
) -> list[SummaryProfileSchema]:
    async with session_factory() as session:
        profiles = await list_summary_profiles(session)
    return [_profile_schema(profile) for profile in profiles]


@router.post("", response_model=SummaryProfileSchema)
async def post_summary_profile(
    payload: SummaryProfileCreateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    actor: Annotated[str, Depends(get_actor)],
) -> SummaryProfileSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            llm_provider = await get_llm_provider(session, payload.llm_provider_id)
            profile = await create_summary_profile(
                session,
                name=payload.name,
                llm_provider=llm_provider,
                model=payload.model,
                prompt_version=payload.prompt_version,
                system_prompt=payload.system_prompt,
                temperature=payload.temperature,
                max_output_tokens=payload.max_output_tokens,
                enabled=payload.enabled,
                is_default=payload.is_default,
                actor=actor,
            )
            return _profile_schema(SummaryProfileView(
                id=profile.id,
                name=profile.name,
                llm_provider=SummaryProfileProviderView(
                    id=llm_provider.id,
                    name=llm_provider.name,
                    provider_type=llm_provider.provider_type,
                ),
                model=profile.model,
                effective_model=profile.model or llm_provider.default_model,
                uses_provider_default_model=profile.model is None,
                prompt_version=profile.prompt_version,
                system_prompt=profile.system_prompt,
                temperature=profile.temperature,
                max_output_tokens=profile.max_output_tokens,
                enabled=profile.enabled,
                is_default=profile.is_default,
            ))
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


@router.patch("/{profile_id}", response_model=SummaryProfileSchema)
async def patch_summary_profile(
    profile_id: int,
    payload: SummaryProfileUpdateRequest,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    actor: Annotated[str, Depends(get_actor)],
) -> SummaryProfileSchema | JSONResponse:
    fields = _provided_fields(payload)
    update_fields = {
        name: getattr(payload, name)
        for name in (
            "name",
            "llm_provider_id",
            "model",
            "prompt_version",
            "system_prompt",
            "temperature",
            "max_output_tokens",
            "enabled",
            "is_default",
        )
        if name in fields
    }
    try:
        async with session_scope(session_factory) as session:
            profile = await update_summary_profile(
                session,
                profile_id=profile_id,
                actor=actor,
                **update_fields,
            )
    except SummaryProfileNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary profile not found",
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
    return _profile_schema(profile)


@router.delete("/{profile_id}", response_model=DeleteResponse)
async def delete_profile(
    profile_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    actor: Annotated[str, Depends(get_actor)],
) -> DeleteResponse | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            await delete_summary_profile(session, profile_id=profile_id, actor=actor)
    except SummaryProfileNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary profile not found",
        )
    except SummaryProfileInUseError as exc:
        return api_error_response(
            status_code=409,
            code="conflict",
            message=str(exc),
        )
    return DeleteResponse(success=True)


@router.post("/{profile_id}/set-default", response_model=SummaryProfileSchema)
async def post_summary_profile_set_default(
    profile_id: int,
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    actor: Annotated[str, Depends(get_actor)],
) -> SummaryProfileSchema | JSONResponse:
    try:
        async with session_scope(session_factory) as session:
            profile = await set_default_summary_profile(
                session,
                profile_id=profile_id,
                actor=actor,
            )
    except SummaryProfileNotFoundError:
        return api_error_response(
            status_code=404,
            code="not_found",
            message="summary profile not found",
        )
    return _profile_schema(profile)
