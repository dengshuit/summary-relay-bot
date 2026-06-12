from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.db.session import session_scope
from summary_relay_bot.services.runtime_config import create_audit_log
from summary_relay_bot.services.telegram_runtime import RuntimeBusyError, TelegramRuntimeManager
from summary_relay_bot.web.deps import get_actor, get_session_factory, get_telegram_runtime
from summary_relay_bot.web.errors import api_error_response
from summary_relay_bot.web.schemas import BotRuntimeReloadResponse


router = APIRouter(prefix="/system", tags=["system"])


@router.post("/reload-bot-runtime", response_model=BotRuntimeReloadResponse)
async def reload_bot_runtime(
    session_factory: Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)],
    telegram_runtime: Annotated[TelegramRuntimeManager | None, Depends(get_telegram_runtime)],
    actor: Annotated[str, Depends(get_actor)],
) -> BotRuntimeReloadResponse | JSONResponse:
    if telegram_runtime is None:
        return api_error_response(
            status_code=409,
            code="runtime_unavailable",
            message="Bot runtime manager is not mounted in this Web API process",
        )
    try:
        await telegram_runtime.reload_from_db()
    except RuntimeBusyError:
        return api_error_response(
            status_code=409,
            code="runtime_busy",
            message="Bot runtime reload is blocked by an active summary; retry after it finishes",
        )

    async with session_scope(session_factory) as session:
        await create_audit_log(
            session,
            actor=actor,
            action="reload_bot_runtime",
            entity_type="system",
            redacted_after={"accepted": True, "operation": "reload_bot_runtime"},
        )
    return BotRuntimeReloadResponse(
        accepted=True,
        status="accepted",
        detail="Bot runtime reload completed",
    )
