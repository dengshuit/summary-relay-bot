from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties

from summary_relay_bot.config import AppConfig

logger = logging.getLogger(__name__)


class WebhookInfoLike(Protocol):
    url: str


class BotTokenConfig(Protocol):
    bot_token: str


@dataclass(frozen=True, slots=True)
class StartupPreflightResult:
    webhook_was_active: bool
    webhook_deleted: bool


class ActiveWebhookError(RuntimeError):
    pass


def create_bot(config: BotTokenConfig) -> Bot:
    return Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )


async def ensure_polling_delivery(bot: Bot, config: AppConfig) -> StartupPreflightResult:
    webhook_info = await bot.get_webhook_info()
    webhook_url = getattr(webhook_info, "url", "") or ""
    if not webhook_url:
        return StartupPreflightResult(webhook_was_active=False, webhook_deleted=False)

    if not config.allow_webhook_delete:
        raise ActiveWebhookError(
            "Telegram webhook is active; polling startup is blocked. "
            "Unset the webhook or set ALLOW_WEBHOOK_DELETE=true to delete it."
        )

    await bot.delete_webhook(
        drop_pending_updates=config.drop_pending_updates_on_webhook_delete,
    )
    return StartupPreflightResult(webhook_was_active=True, webhook_deleted=True)
