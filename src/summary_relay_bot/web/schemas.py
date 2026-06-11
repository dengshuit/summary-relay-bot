from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class SecretStateSchema(BaseModel):
    configured: bool
    updated_at: datetime | None = None


class BotInstanceSchema(BaseModel):
    id: int
    name: str
    owner_id_redacted: str
    telegram_bot_id: int | None = None
    telegram_username: str | None = None
    enabled: bool
    status: str
    needs_restart: bool
    last_validated_at: datetime | None = None
    secret: SecretStateSchema


class BotListResponse(BaseModel):
    active: BotInstanceSchema | None
    items: list[BotInstanceSchema]


class BotUpdateRequest(BaseModel):
    id: int
    name: str | None = None
    owner_id: int | None = None
    enabled: bool | None = None
    bot_token: str | None = None


class BotValidateRequest(BaseModel):
    id: int
    bot_token: str | None = None


class BotValidateResponse(BaseModel):
    status: str
    last_validated_at: datetime
    telegram_bot_id: int | None = None
    telegram_username: str | None = None
    error_type: str | None = None
    error_message: str | None = None


class LLMProviderSchema(BaseModel):
    id: int
    name: str
    provider_type: str
    base_url: str | None = None
    default_model: str
    timeout_seconds: int
    max_retries: int
    enabled: bool
    status: str
    last_validated_at: datetime | None = None
    secret: SecretStateSchema


class LLMProviderListResponse(BaseModel):
    items: list[LLMProviderSchema]


class LLMProviderCreateRequest(BaseModel):
    name: str
    provider_type: str
    base_url: str | None = None
    api_key: str
    default_model: str
    timeout_seconds: int = 30
    max_retries: int = 2
    enabled: bool = True


class LLMProviderUpdateRequest(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    default_model: str | None = None
    timeout_seconds: int | None = None
    max_retries: int | None = None
    enabled: bool | None = None


class LLMProviderTestResponse(BaseModel):
    status: str
    last_validated_at: datetime
    error_type: str | None = None
    error_message: str | None = None


class SummaryProfileProviderSchema(BaseModel):
    id: int
    name: str
    provider_type: str


class SummaryProfileSchema(BaseModel):
    id: int
    name: str
    llm_provider: SummaryProfileProviderSchema
    model: str | None = None
    effective_model: str
    uses_provider_default_model: bool
    prompt_version: str
    system_prompt: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    enabled: bool
    is_default: bool


class SummaryProfileListResponse(BaseModel):
    items: list[SummaryProfileSchema]


class SummaryProfileCreateRequest(BaseModel):
    name: str
    llm_provider_id: int
    model: str | None = None
    prompt_version: str = "v1"
    system_prompt: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    enabled: bool = True
    is_default: bool = False


class SummaryProfileUpdateRequest(BaseModel):
    name: str | None = None
    llm_provider_id: int | None = None
    model: str | None = None
    prompt_version: str | None = None
    system_prompt: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    enabled: bool | None = None
    is_default: bool | None = None


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


class GroupSummarySettingsSchema(BaseModel):
    enabled: bool
    interval_minutes: int
    summary_profile_id: int | None = None
    timezone: str


class EffectiveSummaryProfileSchema(BaseModel):
    id: int
    name: str


class GroupLastSummarySchema(BaseModel):
    status: str
    finished_at: datetime | None = None
    error_type: str | None = None


class GroupSummaryStateSchema(BaseModel):
    last_summary_sequence: int
    last_summary_at: datetime | None = None


class SummaryJobResultSchema(BaseModel):
    id: int
    prompt_version: str
    llm_provider_id: int | None = None
    summary_profile_id: int | None = None
    model: str | None = None
    interval_start_sequence: int
    interval_end_sequence: int
    created_at: datetime


class SummaryJobSchema(BaseModel):
    id: int
    group_id: int
    chat_id: int
    trigger_type: str
    status: str
    starting_sequence: int
    cutoff_sequence: int | None = None
    prompt_version: str | None = None
    llm_provider_id: int | None = None
    summary_profile_id: int | None = None
    model: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_type: str | None = None
    error_message: str | None = None
    result: SummaryJobResultSchema | None = None


class GroupListItemSchema(BaseModel):
    id: int
    chat_id: int
    chat_type: str
    title: str | None = None
    username: str | None = None
    discovered_at: datetime
    settings: GroupSummarySettingsSchema
    effective_profile: EffectiveSummaryProfileSchema | None = None
    last_summary: GroupLastSummarySchema | None = None


class GroupListResponse(BaseModel):
    items: list[GroupListItemSchema]
    next_cursor: str | None = None


class GroupDetailSchema(GroupListItemSchema):
    summary_state: GroupSummaryStateSchema | None = None
    active_job: SummaryJobSchema | None = None
    recent_jobs: list[SummaryJobSchema]


class GroupSummarySettingsUpdateRequest(BaseModel):
    enabled: bool
    interval_minutes: int
    summary_profile_id: int | None = None
    timezone: str = "UTC"


class TriggerSummaryJobResponse(BaseModel):
    job: SummaryJobSchema
    poll_url: str


class AuditLogSchema(BaseModel):
    id: int
    actor: str
    action: str
    entity_type: str
    entity_id: str | None = None
    redacted_before: dict[str, Any] | None = None
    redacted_after: dict[str, Any] | None = None
    created_at: datetime


class AuditLogListResponse(BaseModel):
    items: list[AuditLogSchema]
    next_cursor: str | None = None
