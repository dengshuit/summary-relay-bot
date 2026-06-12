# WebUI API contract alignment

## Goal

Make the rewritten `web/` application the single source of truth for the
management WebUI API contract.

The current WebUI is the intended product experience and is the only frontend
client. Backend API responses should be shaped for this WebUI directly where it
represents real product needs, while preserving security boundaries for secrets,
owner IDs, admin tokens, and raw group message content.

This task plans the API and frontend contract refactor. It does not implement
the changes until the plan is reviewed and the task is started.

## Confirmed Facts

- The rewritten frontend lives in `web/` and calls `/api/*` through
  `web/src/api/client.ts`.
- The frontend currently expects WebUI-oriented fields from the mock server in
  `web/server.ts`.
- The existing backend routes are under `src/summary_relay_bot/web/routes/`.
- Existing authenticated API routes:
  - `GET /api/dashboard`
  - `GET|POST|PATCH /api/bot`
  - `POST /api/bot/validate`
  - `GET|POST /api/llm-providers`
  - `PATCH /api/llm-providers/{provider_id}`
  - `POST /api/llm-providers/{provider_id}/test`
  - `GET|POST /api/summary-profiles`
  - `PATCH /api/summary-profiles/{profile_id}`
  - `POST /api/summary-profiles/{profile_id}/set-default`
  - `GET /api/groups`
  - `GET /api/groups/{group_id}`
  - `PATCH /api/groups/{group_id}/summary-settings`
  - `POST /api/groups/{group_id}/summary-jobs`
  - `GET /api/groups/{group_id}/summary-jobs/{job_id}`
  - `GET /api/audit-logs`
- Backend Bot runtime hot reload now exists:
  - `POST /api/bot` with `enabled=true` attempts runtime convergence.
  - `PATCH /api/bot` reloads runtime for non-empty token, owner, or enabled
    changes.
  - Busy runtime reload returns `409 runtime_busy` before committing the
    requested change.
  - Successful runtime convergence clears relevant `needs_restart` flags.
- Dashboard now reads `TelegramRuntimeManager.state_snapshot()` when a runtime
  manager is mounted.
- There is no current backend `POST /api/system/restart` route.
- Existing backend `GET /api/bot` returns `active` as a Bot object; the current
  WebUI expects the active Bot ID.
- Existing backend Provider/Profile list routes return `{ items }`; the current
  WebUI expects direct arrays.
- The current WebUI still sends Bot validation as `{ temporary_token }`, while
  the backend expects `{ id, bot_token? }`.
- Backend data already stores summary job metadata and generated summary text:
  `summary_jobs` plus `summary_results.summary_text`.
- There is no current backend `GET /api/summaries`.
- Private relay persistence already exists:
  - models: `PrivateUser`, `PrivateMessage`, `AdminReplyMap`,
    `DeliveryAttempt`
  - service: `src/summary_relay_bot/services/private_relay.py`
  - unit tests: `tests/unit/test_private_relay.py`
- There is no current backend `GET /api/private-relays`.
- The current WebUI calls missing Provider/Profile endpoints:
  - `DELETE /api/llm-providers/{id}`
  - `POST /api/llm-providers/fetch-models`
  - `GET /api/llm-providers/{id}/models`
  - `DELETE /api/summary-profiles/{id}`
- `LLMProvider` currently stores `default_model` but has no persisted supported
  model list.
- Current frontend data types still use string IDs, while backend IDs are
  numeric database IDs.
- `GroupDetail` currently starts polling with
  `/api/summary-jobs/{groupId}/{jobId}/poll`, but the backend route is
  `/api/groups/{group_id}/summary-jobs/{job_id}`.
- `AuditLog.redacted_before` and `redacted_after` are already JSON objects from
  the backend, but the current frontend types still model them as strings.
- Existing backend tests assert that Bot tokens, LLM API keys,
  `WEBUI_ADMIN_TOKEN`, `SETTINGS_ENCRYPTION_KEY`, raw owner IDs, and raw group
  message bodies do not leak from management APIs.
- User decision: current WebUI is the only client; backend API contracts may be
  reshaped to fit this WebUI directly.

## Requirements

- Treat the rewritten WebUI as the only frontend client and define a
  WebUI-first API response contract.
- Prefer backend response changes for fields that represent real WebUI product
  data needs.
- Keep frontend-only fixes in the frontend when they are not backend product
  data:
  - numeric IDs vs string-only select values
  - Bot validation payload wiring
  - AuditLog JSON object rendering
  - GroupDetail job polling URL
  - mock-data fallback removal or development-only fencing
- Preserve all existing secret-safe boundaries:
  - never expose Bot token, LLM API key, encrypted secret values,
    `WEBUI_ADMIN_TOKEN`, `SETTINGS_ENCRYPTION_KEY`, or raw owner ID
  - do not expose raw group message bodies through management APIs
  - keep request validation errors redacted
- Preserve existing Bot runtime hot reload semantics:
  - Bot create/update should continue to converge runtime without restarting the
    Web API process when a runtime manager is mounted.
  - `runtime_busy` should remain a 409 and should not commit the requested
    runtime-affecting Bot change.
  - `needs_restart` should mean "runtime convergence still pending or failed",
    not "operator must restart the whole process".
- If the Dashboard keeps an apply/reload button, expose it as a Bot runtime
  reload operation, not a process restart:
  - preferred route: `POST /api/system/reload-bot-runtime`
  - behavior: call `telegram_runtime.reload_from_db()` when a runtime manager is
    available, return 409 when busy, and return an explicit unavailable message
    when the Web API is running without a runtime manager
- Shape existing backend APIs for the current WebUI:
  - Bot list returns `active` as the active Bot ID plus `items`
  - Bot validation returns UI-friendly success/detail fields alongside status
  - LLM Provider list returns an array directly
  - LLM Provider test returns UI-friendly success/detail fields
  - Summary Profile list returns an array directly with flat provider fields
  - Dashboard returns WebUI chart fields and provider display fields
  - Group list/detail include effective profile display fields
  - Summary job responses include display-ready sequence/provider/profile fields
  - Group settings update returns updated group detail
- Add `GET /api/summaries` for historical summary records.
- Add read-only `GET /api/private-relays` for the current Private Relays page
  and Dashboard private-user ranking.
- Add Provider supported model storage and API surface:
  - persist a model list on `llm_providers` through a JSON column
  - accept `models` on Provider create/update
  - return `models` on Provider responses
  - expose `GET /api/llm-providers/{id}/models`
  - expose `POST /api/llm-providers/fetch-models` for temporary upstream fetch
- Add delete endpoints only with conservative integrity constraints:
  - Provider delete must be rejected when referenced by Summary Profiles,
    Summary Jobs, or Summary Results.
  - Summary Profile delete must be rejected when it is default, referenced by
    Group Summary Settings, Summary Jobs, or Summary Results.
  - Successful deletes must write redacted audit logs.
- Update frontend types and call sites to the final WebUI-first contract.
- Update backend and frontend tests to match the new contract.
- Keep the production static serving contract intact: `/api/*` remains backend
  JSON API, non-API SPA routes fall back to the built React app.

## Acceptance Criteria

- [ ] `prd.md`, `design.md`, and `implement.md` exist for this task and define
      the API contract refactor before implementation begins.
- [ ] Backend route schemas match the rewritten WebUI contract for Bot,
      LLM Provider, Summary Profile, Dashboard, Groups, summary jobs, summaries,
      private relays, and audit logs.
- [ ] Bot create/update retains hot reload behavior, including `409
      runtime_busy` and restart-flag semantics.
- [ ] Dashboard no longer depends on a fake process restart. Any apply button
      uses Bot runtime reload semantics or is hidden when reload is unavailable.
- [ ] `GET /api/summaries` returns paginated historical summary records with
      group metadata, job metadata, provider/profile display fields, sequence
      range, and generated summary content when available.
- [ ] `GET /api/private-relays` returns paginated private relay records, reply
      map metadata, delivery status, safe private-user metadata, and aggregate
      status counts.
- [ ] Provider responses include persisted `models`, and Provider create/update
      can replace that list without exposing API keys.
- [ ] Provider model fetch can retrieve upstream model IDs for supported
      provider types without persisting temporary API keys.
- [ ] Provider/Profile delete endpoints reject in-use resources with a clear
      conflict response and audit successful deletes.
- [ ] Dashboard returns `summary_24h.trend`,
      `summary_24h.group_distribution`, `default_profile.provider_name`, and
      `bot.telegram_identity`.
- [ ] Bot and LLM validation/test endpoints return UI-friendly `success` and
      `detail` fields without removing useful status/error fields.
- [ ] Current WebUI pages can consume backend responses without depending on
      `web/server.ts` mock response shapes.
- [ ] Backend tests cover changed contracts and new endpoints, including auth
      requirements and redaction.
- [ ] Frontend typecheck and production build pass.
- [ ] Relevant backend unit/integration tests pass.
- [ ] A manual WebUI smoke check covers Login, Dashboard, Bot, Engine, Groups,
      GroupDetail, Summaries, PrivateRelays, and AuditLogs against the real
      backend API.

## Out Of Scope

- Replacing the current WebUI design or visual layout.
- Reintroducing the old Semi-based business pages.
- Changing Telegram polling behavior beyond the existing Bot runtime reload
  path.
- Adding multi-admin auth, RBAC, sessions, cookies, or username/password login.
- Exposing plaintext secrets or raw group message bodies.
- Implementing a real process restart mechanism.
- Adding write/reply operations to the Private Relays WebUI beyond the current
  read-only page.
- Soft-delete/archive behavior for Provider/Profile unless explicitly chosen as
  a later product decision.

## Resolved Decisions

- Provider/Profile deletion policy: hard delete is allowed only when the
  resource is not referenced. Referenced resources return `409 conflict`.
  Soft-delete/archive behavior remains out of scope.
