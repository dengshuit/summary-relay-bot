from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import BootstrapConfig
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.web.auth import require_admin_token
from summary_relay_bot.web.errors import WebUnauthorizedError, unauthorized_exception_handler
from summary_relay_bot.web.routes.bot import router as bot_router
from summary_relay_bot.web.routes.dashboard import router as dashboard_router


def create_web_app(
    *,
    bootstrap_config: BootstrapConfig,
    session_factory: async_sessionmaker[AsyncSession],
    secret_service: SecretService,
    telegram_startup: object,
) -> FastAPI:
    app = FastAPI(title="Summary Relay Bot Web API")
    app.state.bootstrap_config = bootstrap_config
    app.state.session_factory = session_factory
    app.state.secret_service = secret_service
    app.state.telegram_startup = telegram_startup
    app.add_exception_handler(WebUnauthorizedError, unauthorized_exception_handler)

    api_router = APIRouter(prefix="/api", dependencies=[Depends(require_admin_token)])
    api_router.include_router(bot_router)
    api_router.include_router(dashboard_router)
    app.include_router(api_router)
    return app
