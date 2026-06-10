from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class TelegramStartupSchema(BaseModel):
    status: str
    detail: str | None = None


class DashboardBotSchema(BaseModel):
    id: int
    name: str
    enabled: bool
    status: str
    needs_restart: bool
    telegram_bot_id: int | None = None
    telegram_username: str | None = None
    last_validated_at: datetime | None = None


class GroupCountsSchema(BaseModel):
    total: int
    enabled: int


class DefaultProfileSchema(BaseModel):
    id: int
    name: str
    enabled: bool
    llm_provider_id: int
    prompt_version: str


class Summary24hSchema(BaseModel):
    total: int
    succeeded: int
    failed: int


class RecentAuditLogSchema(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    created_at: datetime


class DashboardResponse(BaseModel):
    telegram_startup: TelegramStartupSchema
    bot: DashboardBotSchema | None
    groups: GroupCountsSchema
    default_profile: DefaultProfileSchema | None
    summary_24h: Summary24hSchema
    restart_pending: list[str]
    recent_audit_logs: list[RecentAuditLogSchema]
