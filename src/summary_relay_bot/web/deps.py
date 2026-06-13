from __future__ import annotations

from typing import cast

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from summary_relay_bot.config import AppConfig, BootstrapConfig
from summary_relay_bot.services.secrets import SecretService
from summary_relay_bot.services.summary_notifications import SummaryNotificationDispatcher
from summary_relay_bot.services.summary_test_tasks import SummaryTestTaskRegistry
from summary_relay_bot.services.userbot_ingestion import DialogDiscoveryProvider
from summary_relay_bot.services.telegram_runtime import TelegramRuntimeManager
from summary_relay_bot.telegram.userbot import (
    UserbotClientConfig,
    UserbotClientFactory,
    create_telethon_dialog_discovery_provider,
)


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


def get_summary_notification_dispatcher(request: Request) -> SummaryNotificationDispatcher | None:
    runtime = get_telegram_runtime(request)
    resources = runtime.resources if runtime is not None else None
    if resources is not None:
        return resources.notification_dispatcher
    return cast(
        SummaryNotificationDispatcher | None,
        getattr(request.app.state, "summary_notification_dispatcher", None),
    )


def get_telegram_startup(request: Request) -> object:
    return _state_value(request, "telegram_startup")


def get_telegram_runtime(request: Request) -> TelegramRuntimeManager | None:
    return cast(TelegramRuntimeManager | None, _state_value(request, "telegram_runtime"))


def get_userbot_client_factory(request: Request) -> UserbotClientFactory | None:
    return cast(UserbotClientFactory | None, getattr(request.app.state, "userbot_client_factory", None))


def get_userbot_dialog_discovery_provider(request: Request) -> DialogDiscoveryProvider | None:
    configured_provider = cast(
        DialogDiscoveryProvider | None,
        getattr(request.app.state, "userbot_dialog_discovery_provider", None),
    )
    if configured_provider is not None:
        return configured_provider

    async def discover_dialogs(runtime_config) -> object:
        provider = create_telethon_dialog_discovery_provider(
            UserbotClientConfig(
                api_id=runtime_config.api_id,
                api_hash=runtime_config.api_hash,
                session_string=runtime_config.session_string,
                proxy_url=runtime_config.proxy_url,
            )
        )
        return await provider()

    return discover_dialogs


def get_actor() -> str:
    return WEBUI_ACTOR
