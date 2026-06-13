export interface SecretState {
  configured: boolean;
  updated_at: string | null;
}

export interface BotInstance {
  id: number;
  name: string;
  owner_id_redacted: string;
  telegram_bot_id: number | null;
  telegram_username: string | null;
  enabled: boolean;
  status: 'unvalidated' | 'valid' | 'invalid' | 'error';
  needs_restart: boolean;
  last_validated_at: string | null;
  secret: SecretState;
}

export interface BotValidationResponse {
  success: boolean;
  detail: string;
  status: 'unvalidated' | 'valid' | 'invalid' | 'error';
  last_validated_at: string;
  bot_id: number | null;
  username: string | null;
  error_type: string | null;
  error_message: string | null;
}

export interface LLMProvider {
  id: number;
  name: string;
  provider_type: 'anthropic' | 'openai' | 'openai_compatible';
  base_url: string | null;
  default_model: string;
  timeout_seconds: number;
  max_retries: number;
  enabled: boolean;
  status: 'unvalidated' | 'valid' | 'invalid' | 'error';
  last_validated_at: string | null;
  secret: SecretState;
  models: string[];
}

export interface SummaryProfile {
  id: number;
  name: string;
  llm_provider_id: number;
  llm_provider_name: string;
  provider_type: string;
  model: string | null; // null means provider default model
  effective_model: string;
  uses_provider_default_model: boolean;
  prompt_version: string;
  system_prompt: string | null;
  temperature: number | null; // 0..2
  max_output_tokens: number | null;
  enabled: boolean;
  is_default: boolean;
}

export interface GroupSummarySettings {
  enabled: boolean;
  interval_minutes: number;
  summary_profile_id: number | null; // null means fallback to default profile
  timezone: string;
}

export interface GroupLastSummary {
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'blocked';
  finished_at: string | null;
  error_type: string | null;
  error_message?: string | null;
}

export interface GroupItem {
  id: number;
  chat_id: number;
  chat_type: string; // group, supergroup, etc.
  title: string | null;
  username: string | null;
  discovered_at: string;
  settings: GroupSummarySettings;
  effective_profile: {
    id: number;
    name: string;
    model: string | null;
    provider: string | null;
  } | null;
  last_summary: GroupLastSummary | null;
}

export interface SummaryJob {
  id: number;
  group_id: number;
  chat_id: number;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'blocked';
  trigger_type: 'manual' | 'scheduled';
  sequence_range: string | null; // e.g. "1001-1050"
  starting_sequence: number;
  cutoff_sequence: number | null;
  prompt_version: string | null;
  llm_provider_id: number | null;
  summary_profile_id: number | null;
  model: string | null;
  provider: string | null;
  profile_name: string | null;
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

export interface SummaryTestTask {
  id: string;
  group_id: number;
  chat_id: number;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'canceled';
  step: 'submitted' | 'queued' | 'running' | 'generating' | 'completed';
  message_count: number | null;
  sequence_range: string | null;
  summary_text: string | null;
  error_type: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface GroupDetail extends GroupItem {
  summary_state: {
    last_summary_sequence: number;
    last_summary_at: string | null;
  } | null;
  active_job: SummaryJob | null;
  recent_jobs: SummaryJob[];
}

export interface AuditLog {
  id: number;
  actor: string;
  action: string; // create, update, delete, etc.
  entity_type: string; // bot, llm_provider, summary_profile, group, etc.
  entity_id: string | null;
  redacted_before: Record<string, unknown> | null;
  redacted_after: Record<string, unknown> | null;
  created_at: string;
}

export interface DashboardAuditLog {
  id: number;
  actor: string;
  action: string;
  entity_type: string;
  entity_id: string | null;
  created_at: string;
}

export interface DashboardData {
  telegram_startup: {
    status: string;
    detail: string | null;
  };
  bot: {
    id: number;
    name: string;
    enabled: boolean;
    status: 'unvalidated' | 'valid' | 'invalid' | 'error';
    needs_restart: boolean;
    telegram_identity: string | null; // e.g. "@my_bot (ID: 12345)"
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
    provider_id: number;
    provider_name: string;
    prompt_version: string;
  } | null;
  summary_24h: {
    total: number;
    succeeded: number;
    failed: number;
    trend: Array<{ time: string; count: number }>;
    group_distribution: Array<{ name: string; value: number }>;
  };
  restart_pending: string[]; // list of items that require restart (e.g. ["bot_token_changed"])
  recent_audit_logs: DashboardAuditLog[];
}

export interface APIError {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
}

export interface HistoricalSummary {
  id: number;
  job_id: number;
  status: 'pending' | 'running' | 'succeeded' | 'failed' | 'blocked';
  trigger_type: 'manual' | 'scheduled';
  sequence_range: string | null;
  model: string | null;
  provider: string | null;
  profile_name: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_type: string | null;
  error_message: string | null;
  group_id: number;
  group_title: string | null;
  group_username: string | null;
  chat_id: number;
  content: string | null;
}

export interface PrivateUser {
  id: number;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
}

export interface ReplyMap {
  source_kind: string;
  status: string;
  admin_message_id: number | null;
}

export interface PrivateRelayItem {
  id: number;
  private_user: PrivateUser;
  direction: 'incoming' | 'outgoing';
  message_type: string;
  text_preview: string | null;
  caption_preview: string | null;
  delivery_status: 'stored' | 'sent' | 'partial_failed' | 'failed' | 'blocked';
  error_type: string | null;
  error_message: string | null;
  telegram_message_id: number | null;
  admin_message_id: number | null;
  reply_maps: ReplyMap[];
  created_at: string;
}

export interface PrivateRelaysResponse {
  items: PrivateRelayItem[];
  next_cursor: string | null;
  stats: {
    total: number;
    sent: number;
    partial_failed: number;
    failed: number;
    blocked: number;
  };
}
