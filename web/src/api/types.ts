export type ValidationStatus = "unvalidated" | "valid" | "invalid" | "error" | string;
export type JobStatus = "pending" | "running" | "succeeded" | "failed" | "blocked" | string;

export interface SecretState {
  configured: boolean;
  updated_at: string | null;
}

export interface ApiErrorPayload {
  error?: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface BotInstance {
  id: number;
  name: string;
  owner_id_redacted: string;
  telegram_bot_id: number | null;
  telegram_username: string | null;
  enabled: boolean;
  status: ValidationStatus;
  needs_restart: boolean;
  last_validated_at: string | null;
  secret: SecretState;
}

export interface BotListResponse {
  active: BotInstance | null;
  items: BotInstance[];
}

export interface BotValidateResponse {
  status: ValidationStatus;
  last_validated_at: string;
  telegram_bot_id: number | null;
  telegram_username: string | null;
  error_type: string | null;
  error_message: string | null;
}

export interface LLMProvider {
  id: number;
  name: string;
  provider_type: "anthropic" | "openai" | "openai_compatible" | string;
  base_url: string | null;
  default_model: string;
  timeout_seconds: number;
  max_retries: number;
  enabled: boolean;
  status: ValidationStatus;
  last_validated_at: string | null;
  secret: SecretState;
}

export interface LLMProviderListResponse {
  items: LLMProvider[];
}

export interface LLMProviderTestResponse {
  status: ValidationStatus;
  last_validated_at: string;
  error_type: string | null;
  error_message: string | null;
}

export interface SummaryProfileProvider {
  id: number;
  name: string;
  provider_type: string;
}

export interface SummaryProfile {
  id: number;
  name: string;
  llm_provider: SummaryProfileProvider;
  model: string | null;
  effective_model: string;
  uses_provider_default_model: boolean;
  prompt_version: string;
  system_prompt: string | null;
  temperature: number | null;
  max_output_tokens: number | null;
  enabled: boolean;
  is_default: boolean;
}

export interface SummaryProfileListResponse {
  items: SummaryProfile[];
}

export interface DashboardResponse {
  telegram_startup: {
    status: string;
    detail: string | null;
  };
  bot: {
    id: number;
    name: string;
    enabled: boolean;
    status: ValidationStatus;
    needs_restart: boolean;
    telegram_bot_id: number | null;
    telegram_username: string | null;
    last_validated_at: string | null;
  } | null;
  groups: {
    total: number;
    enabled: number;
  };
  default_profile: {
    id: number;
    name: string;
    enabled: boolean;
    llm_provider_id: number;
    prompt_version: string;
  } | null;
  summary_24h: {
    total: number;
    succeeded: number;
    failed: number;
  };
  restart_pending: string[];
  recent_audit_logs: RecentAuditLog[];
}

export interface RecentAuditLog {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
}

export interface GroupSummarySettings {
  enabled: boolean;
  interval_minutes: number;
  summary_profile_id: number | null;
  timezone: string;
}

export interface GroupListItem {
  id: number;
  chat_id: number;
  chat_type: string;
  title: string | null;
  username: string | null;
  discovered_at: string;
  settings: GroupSummarySettings;
  effective_profile: {
    id: number;
    name: string;
  } | null;
  last_summary: {
    status: JobStatus;
    finished_at: string | null;
    error_type: string | null;
  } | null;
}

export interface GroupListResponse {
  items: GroupListItem[];
  next_cursor: string | null;
}

export interface SummaryJob {
  id: number;
  group_id: number;
  chat_id: number;
  trigger_type: string;
  status: JobStatus;
  starting_sequence: number;
  cutoff_sequence: number | null;
  prompt_version: string | null;
  llm_provider_id: number | null;
  summary_profile_id: number | null;
  model: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_type: string | null;
  error_message: string | null;
  result: {
    id: number;
    prompt_version: string;
    llm_provider_id: number | null;
    summary_profile_id: number | null;
    model: string | null;
    interval_start_sequence: number;
    interval_end_sequence: number;
    created_at: string;
  } | null;
}

export interface GroupDetail extends GroupListItem {
  summary_state: {
    last_summary_sequence: number;
    last_summary_at: string | null;
  } | null;
  active_job: SummaryJob | null;
  recent_jobs: SummaryJob[];
}

export interface TriggerSummaryJobResponse {
  job: SummaryJob;
  poll_url: string;
}

export interface AuditLog {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  redacted_before: Record<string, unknown> | null;
  redacted_after: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditLogListResponse {
  items: AuditLog[];
  next_cursor: string | null;
}
