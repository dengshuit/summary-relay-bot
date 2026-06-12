# WebUI API Contract Alignment Design

## Architecture

The Python FastAPI backend becomes the WebUI-specific management API for the
rewritten React app in `web/`. Because the rewritten WebUI is the only client,
the backend may return display-ready shapes for this UI instead of preserving
older generic response envelopes.

The design still keeps hard security boundaries in the backend. Frontend
convenience must never cause raw secret values, encrypted secret material,
administrator tokens, encryption keys, raw Telegram owner IDs, or raw group
message bodies to appear in API responses, errors, logs, or audits.

## Boundaries

- Backend API routes remain mounted under `/api` and protected by
  `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`.
- Static SPA fallback must continue to exclude `/api/*`.
- The frontend should call only the Python backend in production.
- `web/server.ts` is treated as a mock/prototype artifact and must not be part
  of the normal production build path.
- Database primary keys remain numeric. UI components that require string
  values can stringify at the component boundary.
- Bot runtime reload is an in-process Telegram runtime operation, not a Web API
  process restart.

## Contract Direction

### Bot

Keep existing paths:

- `GET /api/bot`
- `POST /api/bot`
- `PATCH /api/bot`
- `POST /api/bot/validate`

Change list response to match current WebUI selection behavior:

```ts
interface BotListResponse {
  active: number | null;
  items: BotInstance[];
}
```

`active` is the ID of the active enabled Bot, not the active object. `items`
contains all Bot instances, including the active one.

Change validation response to include UI-friendly fields:

```ts
interface BotValidateResponse {
  success: boolean;
  detail: string;
  status: string;
  last_validated_at: string;
  bot_id: number | null;
  username: string | null;
  error_type: string | null;
  error_message: string | null;
}
```

Request payload should use the current backend's explicit shape:

```ts
interface BotValidateRequest {
  id: number;
  bot_token?: string | null;
}
```

The frontend should map its temporary-token input to `bot_token`. Temporary
non-empty `bot_token` validation must not replace stored token material.

Runtime behavior remains:

- `POST /api/bot` with `enabled=true` attempts `reload_after_change`.
- `PATCH /api/bot` attempts `reload_after_change` for non-empty token, owner, or
  enabled-state changes.
- If a Bot-delivering summary is active, reload-required writes return
  `409 runtime_busy` before committing the change.
- Successful runtime convergence clears relevant `needs_restart` flags.
- Failed runtime convergence returns the safe Bot response shape and leaves
  `needs_restart=true`.

### Bot Runtime Reload

Do not add `POST /api/system/restart` as a real process restart route.

If the Dashboard keeps the apply button, expose:

```text
POST /api/system/reload-bot-runtime
```

Response:

```ts
interface BotRuntimeReloadResponse {
  accepted: boolean;
  status: string;
  detail: string;
}
```

Behavior:

- With a mounted `TelegramRuntimeManager`, call `reload_from_db()`.
- On `RuntimeBusyError`, return `409 runtime_busy`.
- If no runtime manager is mounted, return an operator-facing unavailable
  response. This may be `409 runtime_unavailable` or `501 runtime_unavailable`;
  implementation should pick one and test it consistently.
- Write an audit log only for an accepted manual reload request.
- Do not terminate or restart the Web API process.

### LLM Providers

Keep existing read/create/update/test paths and add delete/model paths:

- `GET /api/llm-providers`
- `POST /api/llm-providers`
- `PATCH /api/llm-providers/{provider_id}`
- `DELETE /api/llm-providers/{provider_id}`
- `POST /api/llm-providers/{provider_id}/test`
- `GET /api/llm-providers/{provider_id}/models`
- `POST /api/llm-providers/fetch-models`

Change list response from an envelope to a direct array:

```ts
type LLMProviderListResponse = LLMProvider[];
```

Provider objects remain redacted and gain a persisted model list:

```ts
interface LLMProvider {
  id: number;
  name: string;
  provider_type: "anthropic" | "openai" | "openai_compatible";
  base_url: string | null;
  default_model: string;
  models: string[];
  timeout_seconds: number;
  max_retries: number;
  enabled: boolean;
  status: string;
  last_validated_at: string | null;
  secret: SecretState;
}
```

Storage:

- Add `llm_providers.models` as a JSON column storing `string[]`.
- Backfill existing rows with `[default_model]`.
- Validate each model ID is non-empty after trimming.
- On Provider create/update, `models` replaces the stored list when supplied.
- Ensure `default_model` remains present in `models`; if omitted from the
  incoming list, prepend it or reject the request. Recommended first pass:
  reject with `400 validation_error` to keep operator intent explicit.

Change provider test response to include WebUI fields while retaining diagnostic
status fields:

```ts
interface LLMProviderTestResponse {
  success: boolean;
  detail: string;
  status: string;
  last_validated_at: string;
  error_type: string | null;
  error_message: string | null;
}
```

Model retrieval:

```ts
interface ProviderModelsResponse {
  success: boolean;
  models: string[];
}
```

`GET /api/llm-providers/{id}/models` returns persisted provider models. If the
stored list is empty for legacy data, return `[default_model]`.

Temporary upstream fetch:

```ts
interface FetchProviderModelsRequest {
  provider_type: "anthropic" | "openai" | "openai_compatible";
  base_url?: string | null;
  api_key?: string | null;
}

interface FetchProviderModelsResponse {
  success: boolean;
  source: string;
  detail: string;
  models: string[];
}
```

Rules:

- The request API key is temporary and must never be stored or audited in
  plaintext.
- For OpenAI and OpenAI-compatible providers, call the `/models` endpoint using
  `base_url` or the OpenAI default base URL.
- For Anthropic, if there is no reliable list endpoint in the current client,
  return a curated static list with `source: "preset"` rather than inventing an
  unsupported network call.
- Network/API failures return a safe error message without echoing the API key.

Deletion:

- `DELETE /api/llm-providers/{id}` returns `{ success: true }` on success.
- Reject with `409 conflict` if referenced by Summary Profiles, Summary Jobs, or
  Summary Results.
- Successful delete writes a redacted audit log.
- Product decision: this endpoint performs hard delete only for unused
  providers; it does not soft-delete or hide referenced providers.

### Summary Profiles

Keep existing read/create/update/set-default paths and add delete:

- `GET /api/summary-profiles`
- `POST /api/summary-profiles`
- `PATCH /api/summary-profiles/{profile_id}`
- `DELETE /api/summary-profiles/{profile_id}`
- `POST /api/summary-profiles/{profile_id}/set-default`

Change list response from an envelope to a direct array and flatten provider
display fields:

```ts
interface SummaryProfile {
  id: number;
  name: string;
  llm_provider_id: number;
  llm_provider_name: string;
  provider_type: string;
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
```

Create/update/set-default responses should return the same flat shape.

Deletion:

- `DELETE /api/summary-profiles/{id}` returns `{ success: true }` on success.
- Reject with `409 conflict` if the profile is default, referenced by Group
  Summary Settings, Summary Jobs, or Summary Results.
- Successful delete writes a redacted audit log.
- Product decision: this endpoint performs hard delete only for unused profiles;
  it does not soft-delete or hide referenced profiles.

### Dashboard

Extend `GET /api/dashboard` for current UI cards and charts:

```ts
interface DashboardResponse {
  telegram_startup: {
    status: string;
    detail: string | null;
  };
  bot: {
    id: number;
    name: string;
    enabled: boolean;
    status: string;
    needs_restart: boolean;
    telegram_identity: string | null;
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
  restart_pending: string[];
  recent_audit_logs: AuditLog[];
}
```

`trend` is generated from summary jobs in the last 24 hours, bucketed into
compact time labels. `group_distribution` is generated from summary jobs/results
joined to group titles. Empty databases return empty arrays.

The Dashboard private-user ranking currently fetches `GET /api/private-relays`
and computes the ranking client-side. That is acceptable for first pass if the
route supports `limit=1000`; a later endpoint can return precomputed rankings if
needed.

### Groups And Summary Jobs

Keep existing group paths.

Extend effective profile display:

```ts
interface EffectiveSummaryProfile {
  id: number;
  name: string;
  model: string | null;
  provider: string | null;
}
```

Return display-ready summary job fields:

```ts
interface SummaryJob {
  id: number;
  group_id: number;
  chat_id: number;
  status: string;
  trigger_type: string;
  sequence_range: string | null;
  model: string | null;
  provider: string | null;
  profile_name: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_type: string | null;
  error_message: string | null;
  result: SummaryJobResult | null;
}
```

The backend may keep internal fields if useful, but frontend-visible fields
above must be stable.

Change group settings update to return full `GroupDetail`, not only settings:

```text
PATCH /api/groups/{group_id}/summary-settings -> GroupDetail
```

The frontend should poll manual jobs through the existing backend route:

```text
GET /api/groups/{group_id}/summary-jobs/{job_id}
```

Do not add a duplicate `/api/summary-jobs/{groupId}/{jobId}/poll` route.

### Historical Summaries

Add:

```text
GET /api/summaries
```

Query parameters:

```text
q?: string
status?: string
group_id?: number
from?: datetime string
to?: datetime string
limit?: number
cursor?: string
```

Response:

```ts
interface HistoricalSummaryListResponse {
  items: HistoricalSummary[];
  next_cursor: string | null;
}

interface HistoricalSummary {
  id: number;
  job_id: number;
  group_id: number;
  group_title: string | null;
  group_username: string | null;
  chat_id: number;
  status: string;
  trigger_type: string;
  sequence_range: string | null;
  model: string | null;
  provider: string | null;
  profile_name: string | null;
  started_at: string | null;
  finished_at: string | null;
  error_type: string | null;
  error_message: string | null;
  content: string | null;
}
```

`content` comes from `summary_results.summary_text`. It is generated output,
not raw message text. Raw group message bodies must remain out of this API.

### Private Relays

Add a read-only route for the current WebUI:

```text
GET /api/private-relays
```

Query parameters:

```text
direction?: "incoming" | "outgoing"
status?: string
q?: string
limit?: number
cursor?: string
```

Response:

```ts
interface PrivateRelaysResponse {
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

interface PrivateRelayItem {
  id: number;
  private_user: {
    id: number;
    telegram_user_id: number;
    username: string | null;
    first_name: string | null;
    last_name: string | null;
  };
  direction: "incoming" | "outgoing";
  message_type: string;
  text_preview: string | null;
  caption_preview: string | null;
  delivery_status: string;
  error_type: string | null;
  error_message: string | null;
  telegram_message_id: number | null;
  admin_message_id: number | null;
  reply_maps: Array<{
    source_kind: string;
    status: string;
    admin_message_id: number | null;
  }>;
  created_at: string;
}
```

Private message previews are product data for the private-relay admin page.
Keep them bounded, for example first 300 characters, and do not expose raw
Telegram update payloads.

### Audit Logs

Keep `GET /api/audit-logs`. Preserve JSON object fields:

```ts
redacted_before: Record<string, unknown> | null;
redacted_after: Record<string, unknown> | null;
```

The frontend should render these objects directly with `JSON.stringify`. Do not
convert audit payloads into JSON strings in the backend.
