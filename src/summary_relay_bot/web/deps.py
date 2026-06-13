from __future__ import annotations

from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig, BootstrapConfig
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.summary_test_tasks import SummaryTestTaskRegistry
from summary_relay_bot.services.telegram_runtime import TelegramRuntimeManager


WEBUI_ACTOR = "webui_admin"


def _state_value(request: Request, name: str) -> object:
    try:
        return getattr(request.app.state, name)
    except AttributeError as exc:
        raise RuntimeError(f"web app state is missing {name}") from exc


def get_bootstrap_config(request: Request) -> BootstrapConfig:
    return cast(BootstrapConfig, _state_value(request, "bootstrap_config"))


def get_app_config(request: Request) -> AppConfig:
    return cast(AppConfig, _state_value(request, "app_config"))


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast(async_sessionmaker[AsyncSession], _state_value(request, "session_factory"))


def get_secret_service(request: Request) -> SecretService:
    return cast(SecretService, _state_value(request, "secret_service"))


def get_summary_test_task_registry(request: Request) -> SummaryTestTaskRegistry:
    return cast(SummaryTestTaskRegistry, _state_value(request, "summary_test_task_registry"))


def get_telegram_startup(request: Request) -> object:
    return _state_value(request, "telegram_startup")


def get_telegram_runtime(request: Request) -> TelegramRuntimeManager | None:
    return cast(TelegramRuntimeManager | None, _state_value(request, "telegram_runtime"))


def get_actor() -> str:
    return WEBUI_ACTOR
