from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.auth import require_admin_token
from summary_relay_bot.web.errors import (
    WebUnauthorizedError,
    request_validation_exception_handler,
    unauthorized_exception_handler,
)
from summary_relay_bot.web.routes.audit_logs import router as audit_logs_router
from summary_relay_bot.web.routes.bot import router as bot_router
from summary_relay_bot.web.routes.dashboard import router as dashboard_router
from summary_relay_bot.web.routes.groups import router as groups_router
from summary_relay_bot.web.routes.llm_providers import router as llm_providers_router
from summary_relay_bot.web.routes.summary_profiles import router as summary_profiles_router
from summary_relay_bot.web.static import mount_webui_static


def create_web_app(
    *,
    bootstrap_config: BootstrapConfig,
    session_factory: async_sessionmaker[AsyncSession],
    secret_service: SecretService,
    telegram_startup: object,
    static_dir: Path | str | None = None,
) -> FastAPI:
    app = FastAPI(title="Summary Relay Bot Web API")
    app.state.bootstrap_config = bootstrap_config
    app.state.session_factory = session_factory
    app.state.secret_service = secret_service
    app.state.telegram_startup = telegram_startup
    app.add_exception_handler(WebUnauthorizedError, unauthorized_exception_handler)
    app.add_exception_handler(RequestValidationError, request_validation_exception_handler)

    api_router = APIRouter(prefix="/api", dependencies=[Depends(require_admin_token)])
    api_router.include_router(bot_router)
    api_router.include_router(dashboard_router)
    api_router.include_router(llm_providers_router)
    api_router.include_router(summary_profiles_router)
    api_router.include_router(groups_router)
    api_router.include_router(audit_logs_router)
    app.include_router(api_router)
    mount_webui_static(app, static_dir=static_dir)
    return app
