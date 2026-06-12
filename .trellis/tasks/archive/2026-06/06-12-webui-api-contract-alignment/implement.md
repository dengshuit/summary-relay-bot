# WebUI API Contract Alignment Implementation Plan

## Preconditions

- Review `prd.md` and `design.md`.
- Provider/Profile delete policy is confirmed: hard delete only when unused,
  otherwise `409 conflict`.
- User reviews and approves the overall implementation plan.
- Run `python3 ./.trellis/scripts/task.py start 06-12-webui-api-contract-alignment`
  before implementation.
- Load `trellis-before-dev` before writing production code.

## Implementation Checklist

1. Baseline and dependency check
   - Confirm current git status and protect unrelated user changes.
   - Run the focused backend tests once if practical to establish baseline:
     - `python3 -m pytest tests/unit/test_web_bot_api.py tests/unit/test_web_llm_provider_api.py tests/unit/test_web_summary_profile_api.py tests/unit/test_web_groups_api.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_audit_logs_api.py tests/integration/test_web_dashboard.py -q`
   - In `web/`, run dependency install only if needed and approved by the
     environment.

2. Add Provider model-list persistence
   - Add `models` / `supported_models` JSON column to `LLMProvider`.
   - Add Alembic migration that backfills existing rows with `[default_model]`.
   - Extend runtime-config Provider view/redacted dict helpers with safe model
     list data.
   - Validate model IDs are non-empty strings and keep `default_model` in the
     stored list.
   - Add model-list persistence tests.

3. Update backend schemas in `src/summary_relay_bot/web/schemas.py`
   - Change Bot list response to `active: int | None`.
   - Add UI-friendly validation/test response fields.
   - Change provider/profile list response shapes to direct arrays or response
     models compatible with direct arrays.
   - Add Provider `models` fields and model-fetch response schemas.
   - Add flat Summary Profile provider fields.
   - Extend Dashboard schemas with `telegram_identity`, provider display fields,
     `trend`, and `group_distribution`.
   - Extend Effective Profile and Summary Job display schemas.
   - Add Historical Summary list/item schemas.
   - Add Private Relay list/item schemas.
   - Add Bot runtime reload response schema if the Dashboard button remains.

4. Update Bot route
   - `GET /api/bot`: return `active` ID and all `items`.
   - `POST /api/bot/validate`: map runtime validation result to
     `success/detail/status/...`.
   - Preserve redaction, temporary token no-persist behavior, hot reload, and
     `runtime_busy` behavior.
   - Update tests in `tests/unit/test_web_bot_api.py`.

5. Add Bot runtime reload route if the Dashboard button remains
   - Add `src/summary_relay_bot/web/routes/system.py`.
   - Expose `POST /api/system/reload-bot-runtime`.
   - Call `telegram_runtime.reload_from_db()` when available.
   - Return `409 runtime_busy` when blocked by an active Bot-delivering summary.
   - Return an explicit unavailable response when no runtime manager is mounted.
   - Add auth, busy, success, unavailable, and redaction/audit tests.
   - Do not add or implement `POST /api/system/restart`.

6. Update LLM Provider route
   - `GET /api/llm-providers`: return array directly while preserving filters.
   - `POST/PATCH /api/llm-providers`: accept and persist `models`.
   - `DELETE /api/llm-providers/{id}`: hard delete only when unused; otherwise
     return `409 conflict`.
   - `GET /api/llm-providers/{id}/models`: return persisted models.
   - `POST /api/llm-providers/fetch-models`: fetch OpenAI/OpenAI-compatible
     `/models` with a temporary key; return preset models for Anthropic unless a
     supported API is implemented.
   - `POST /api/llm-providers/{id}/test`: return
     `success/detail/status/error...`.
   - Preserve secret redaction and no plaintext audit behavior for test/fetch
     calls.
   - Update tests in `tests/unit/test_web_llm_provider_api.py`.

7. Update Summary Profile route
   - Return direct arrays for list.
   - Return flat provider fields for list/create/update/set-default.
   - `DELETE /api/summary-profiles/{id}`: hard delete only when unused and not
     default; otherwise return `409 conflict`.
   - Preserve default switching semantics and validation.
   - Update tests in `tests/unit/test_web_summary_profile_api.py`.

8. Update Dashboard route
   - Join default profile to provider display name.
   - Add `telegram_identity` derived from username and Bot ID.
   - Build 24h trend buckets from `SummaryJob.created_at`.
   - Build group distribution from recent 24h summary jobs/results joined to
     `GroupChat`.
   - Keep empty database response stable with empty arrays.
   - Make restart/apply messaging align with runtime reload state.
   - Update `tests/integration/test_web_dashboard.py`.

9. Update Groups and Summary Job route
   - Extend effective profile helper with model/provider display fields.
   - Extend summary job helper with `sequence_range`, `provider`, and
     `profile_name`.
   - Change `PATCH /api/groups/{id}/summary-settings` response to updated
     `GroupDetail`.
   - Keep trigger/poll auth, conflict, and redaction behavior.
   - Update `tests/unit/test_web_groups_api.py` and
     `tests/unit/test_web_summary_jobs_api.py`.

10. Add summaries route
    - Add `src/summary_relay_bot/web/routes/summaries.py`.
    - Include the router in `src/summary_relay_bot/web/app.py`.
    - Query `SummaryJob` joined to `GroupChat`, optional `SummaryResult`,
      optional provider/profile records.
    - Support `q`, `status`, `group_id`, `from`, `to`, `limit`, `cursor`.
    - Return generated summary text as `content`; never return raw message text.
    - Add `tests/unit/test_web_summaries_api.py` covering:
      - successful list with content
      - filters and pagination
      - failed/pending jobs with `content: null`
      - auth required
      - no secret/admin/encryption/raw-message leaks

11. Add private relays route
    - Add `src/summary_relay_bot/web/routes/private_relays.py`.
    - Include the router in `src/summary_relay_bot/web/app.py`.
    - Query `PrivateMessage` joined to `PrivateUser` and `AdminReplyMap`.
    - Support `direction`, `status`, `q`, `limit`, `cursor`.
    - Return bounded `text_preview` and `caption_preview`.
    - Return aggregate stats for delivery statuses.
    - Add `tests/unit/test_web_private_relays_api.py` covering:
      - successful list with reply maps
      - filters, search, pagination, and stats
      - auth required
      - no Bot token, LLM key, owner ID, admin token, encryption key, or raw
        Telegram update payload leaks

12. Update frontend API types and client
    - Align `web/src/api/types.ts` with final schemas.
    - Align `web/src/api/client.ts` request/response types.
    - Remove list envelope handling where backend now returns arrays.
    - Send Bot validate payload as `{ id, bot_token? }`.
    - Use numeric IDs in data types and stringify only for select values.
    - Change AuditLog redacted fields to object types and render with
      `JSON.stringify`.
    - Change GroupDetail polling URL to
      `/api/groups/{group_id}/summary-jobs/{job_id}`.

13. Update frontend pages for final contract
    - Dashboard: consume backend trend/distribution/provider fields directly.
    - Dashboard: replace `/api/system/restart` with
      `/api/system/reload-bot-runtime` or hide the button if unavailable.
    - Dashboard and PrivateRelays: remove or development-fence mock data
      fallbacks.
    - Bot: use active ID and validation response detail.
    - Engine: consume direct provider/profile arrays, Provider `models`, and
      flat profile provider fields.
    - Groups/GroupDetail: consume extended effective profile/job fields and
      updated group detail after settings save.
    - Summaries: consume `GET /api/summaries`, optionally pass query filters.
    - AuditLogs: render JSON objects directly.

14. Normalize frontend build/dev setup
    - Make `npm run dev` target Vite for real API integration.
    - Keep or remove `web/server.ts` based on decision:
      - preferred: remove from normal scripts and treat it as obsolete mock
      - if retained, clearly name it as mock-only and keep it out of production
        build expectations
    - Remove mock-only dependencies only if they are no longer referenced.

15. Documentation/spec updates
    - Update `.trellis/spec/backend/web-api-contracts.md` with the new
      WebUI-first contracts and security rules.
    - Update `README.md` / `README.zh-CN.md` only if run commands or WebUI
      behavior changed materially.

## Validation Commands

Backend focused tests:

```bash
python3 -m pytest tests/unit/test_web_bot_api.py tests/unit/test_web_llm_provider_api.py tests/unit/test_web_summary_profile_api.py tests/unit/test_web_groups_api.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_audit_logs_api.py tests/unit/test_web_summaries_api.py tests/unit/test_web_private_relays_api.py tests/integration/test_web_dashboard.py -q
```

Backend broader smoke:

```bash
python3 -m pytest tests/unit/test_web_* tests/integration/test_web_dashboard.py -q
python3 -m compileall -q src tests migrations
```

Frontend:

```bash
cd web
npm run lint
npm run build
```

Manual smoke:

- Run backend with real WebUI static/dev setup.
- Log in with `WEBUI_ADMIN_TOKEN`.
- Visit:
  - `/`
  - `/bot`
  - `/engine`
  - `/groups`
  - `/groups/{id}`
  - `/summaries`
  - `/private-relays`
  - `/audit-logs`
- Confirm no page depends on `web/server.ts` mock-only fields.
- Confirm Bot config changes apply through hot reload without restarting the Web
  API process when runtime is available.

## Risk Points

- Response-shape changes will require coordinated backend tests and frontend
  type updates in the same implementation branch.
- Provider `models` requires a DB migration; legacy databases need a safe
  backfill from `default_model`.
- Provider model fetching can leak temporary API keys if error handling is not
  redacted; tests must cover malformed and failed fetch paths.
- Delete endpoints can break historical references if constraints are too
  permissive; keep first pass conflict-only for referenced resources.
- Dashboard chart aggregation can accidentally become expensive; keep the first
  pass limited to 24h and modest grouping.
- Summary list must expose generated summaries but not raw source message text.
- Private relay previews intentionally expose private-message content to the
  authenticated admin UI; keep previews bounded and avoid raw update payloads.
- Bot runtime reload must keep current "busy before commit" semantics.
- Removing mock dependencies can create package-lock churn; keep dependency
  cleanup scoped to actually unused packages.

## Rollback Points

- Provider model persistence can be reverted with its migration before release;
  after release, add a down migration only if the deployment process supports it.
- Bot runtime reload route can be omitted or reverted without blocking automatic
  Bot create/update hot reload.
- Summaries route can be reverted independently if needed.
- Private relays route can be reverted independently if the page is temporarily
  hidden.
- Frontend mock fallback removal can be reverted without touching backend
  contracts.
