# Web API Contracts

## Scenario: Bot Instance Management API

### 1. Scope / Trigger

- Trigger: adding or changing `/api/bot` management endpoints.
- Applies to FastAPI routes under `src/summary_relay_bot/web/routes/bot.py`, schemas in `src/summary_relay_bot/web/schemas.py`, frontend API methods in `web/src/api/client.ts`, Bot runtime rules in `src/summary_relay_bot/services/runtime_config.py`, and runtime coordination in `src/summary_relay_bot/services/telegram_runtime.py`.
- Secret-bearing fields include Bot token, `WEBUI_ADMIN_TOKEN`, and `SETTINGS_ENCRYPTION_KEY`; owner ID is sensitive and must be redacted in responses/audit output.

### 2. Signatures

- `GET /api/bot`
- `POST /api/bot`
- `PATCH /api/bot`
- `POST /api/bot/validate`
- `POST /api/system/reload-bot-runtime`
- Runtime-coordinated `POST /api/bot` / `PATCH /api/bot` may return `409 runtime_busy`.

### 3. Contracts

- All endpoints are mounted below `/api` and require `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`.
- Bot response exposes `owner_id_redacted`, never raw `owner_id`.
- Bot response exposes `secret: { configured: bool, updated_at: datetime | null }`, never `bot_token` or encrypted secret values.
- `GET /api/bot` returns `active: int | null` as the active Bot ID and `items` containing all Bot instances, including the active one.
- `POST /api/bot` requires `name`, `owner_id`, and `bot_token`; `enabled` defaults to `true`.
- `POST /api/bot` with `enabled=true` is reload-required: after the row is created, the server must try to converge the in-process Telegram runtime without restarting Web API.
- `PATCH /api/bot` treats `bot_token` as:
  - missing: no change
  - `null`: no change
  - empty string or whitespace-only string: no change
  - non-empty string: replace encrypted secret, reset validation identity/status, and mark restart required
- Reload-required `PATCH /api/bot` fields are non-empty `bot_token`, non-null `owner_id`, and non-null `enabled`.
- Name-only updates, validation status changes, Telegram identity fields, and blank/null/missing `bot_token` must not trigger runtime reload.
- `POST /api/bot/validate` may accept a temporary non-empty `bot_token`; validation with a temporary token must not replace stored encrypted token material.
- `POST /api/bot/validate` returns UI-facing `success` and `detail` fields alongside validation status and safe identity fields.
- `POST /api/system/reload-bot-runtime` calls the mounted Telegram runtime manager, returns `409 runtime_busy` if a Bot-delivering summary blocks reload, returns `409 runtime_unavailable` when no runtime manager is mounted, and must not restart the Web API process.
- Enabling one Bot instance disables any previously enabled Bot instance and marks affected instances restart-required.
- Runtime reload must rebuild the aiogram Bot, Dispatcher, owner filters, command menus, scheduler, and scheduled summary jobs.
- Successful runtime convergence clears `needs_restart` for affected Bot instances. Failed convergence keeps `needs_restart=true` and exposes only safe runtime state.
- If a Bot-delivering summary is active, reload-required Bot changes must fail before saving with `409 runtime_busy`; old runtime remains unchanged.

### 4. Validation & Error Matrix

- Missing or invalid auth -> `401 {"error": {"code": "unauthorized", "message": "认证失败"}}`.
- Empty `name` on create/update -> `400 validation_error`.
- Empty `bot_token` on create -> `400 validation_error`.
- `owner_id <= 0` on create/update -> `400 validation_error`.
- Creating an enabled Bot while another Bot is enabled -> `400 validation_error`.
- Reload-required create/update while a Bot-delivering summary is active -> `409 runtime_busy` with `{"error": {"code": "runtime_busy", "message": "Bot runtime reload is blocked by an active summary; retry after it finishes"}}`; the requested config change is not committed.
- Manual runtime reload without a mounted runtime manager -> `409 runtime_unavailable`.
- Reload build/start failure after a config write -> response still follows the normal safe Bot response shape, `needs_restart` remains true, and dashboard runtime state reports a safe failure detail.
- `POST /api/system/restart` must not be implemented.
- Missing Bot ID on patch/validate -> `404 not_found`.
- FastAPI request validation errors must use the redacted `request validation failed` response and must not echo request input.

### 5. Good/Base/Bad Cases

- Good: `POST /api/bot` with valid name, owner ID, and Bot token creates an encrypted Bot instance, returns only redacted owner/secret state, and writes redacted audit.
- Good: `PATCH /api/bot` with `{"owner_id": <positive int>}` while no Bot-delivering summary is active applies the DB change, rebuilds runtime owner-bound resources, clears relevant `needs_restart`, and returns only redacted owner/secret state.
- Base: `PATCH /api/bot` with `{}` or blank `bot_token` returns the Bot without changing encrypted token material.
- Base: `PATCH /api/bot` with only `name` updates the DB/audit path and does not call the runtime manager.
- Bad: committing a non-empty token, owner, or enabled-state change and then returning `409 runtime_busy`; busy checks must happen before the config write.
- Bad: adding a process restart API or wiring Dashboard actions to `/api/system/restart`; the supported operation is Bot runtime reload only.
- Bad: returning a raw `owner_id`, `bot_token`, encrypted secret, admin token, or encryption key from any Bot endpoint or audit payload.

### 6. Tests Required

- Auth protection for read, create, patch, and validate endpoints.
- Read/create/update responses do not contain Bot token, raw owner ID, admin token, or encryption key.
- Bot create trims required text, encrypts token, and writes redacted audit.
- Bot blank/null/missing `bot_token` on patch is a no-op.
- Bot non-empty `bot_token` on patch replaces encrypted value and audit remains redacted.
- Bot validation with a temporary token does not replace the stored token.
- Enabling a Bot leaves exactly one enabled Bot.
- Runtime manager start/stop/reload tests cover no-enabled-bot, successful hot start, failed reload preserving `needs_restart`, and busy summary conflict.
- Bot route tests cover enabled create hot start, token/owner/enabled reload, name-only no reload, blank token no reload, and `409 runtime_busy` with no DB commit.
- System route tests cover successful `reload-bot-runtime`, busy, unavailable, auth required, audit, and absence of a restart endpoint.
- Malformed request validation does not echo secret-bearing input.

### 7. Wrong vs Correct

#### Wrong

```python
return {"owner_id": bot.owner_id, "bot_token": payload.bot_token}
```

This leaks raw owner ID and Bot token into the response.

#### Correct

```python
return BotInstanceSchema(
    id=bot.id,
    name=bot.name,
    owner_id_redacted=redact_owner_id(bot.owner_id) or "",
    secret=SecretStateSchema(configured=bool(bot.bot_token_encrypted), updated_at=None),
    ...,
)
```

Return only the redacted owner ID and secret configured state; keep encryption/decryption inside the service layer.

#### Wrong

```python
bot = await update_bot_instance(session, **reload_required_fields)
if await gate.has_active_bot_delivery_summary():
    return runtime_busy()
```

This commits the config before checking whether reload is allowed.

#### Correct

```python
if not await reload_gate.try_begin_runtime_reload():
    return runtime_busy()
bot = await update_bot_instance(session, **reload_required_fields)
await telegram_runtime.reload_from_db()
```

Check the reload gate before mutating Bot runtime fields; release the gate after runtime convergence or failure.

## Scenario: LLM Provider / Summary Profile Management API

### 1. Scope / Trigger

- Trigger: adding or changing `/api/*` management endpoints.
- Applies to FastAPI routes under `src/summary_relay_bot/web/routes/`, schemas in `src/summary_relay_bot/web/schemas.py`, and business rules in `src/summary_relay_bot/services/runtime_config.py`.
- Secret-bearing fields include Bot token, LLM API key, `WEBUI_ADMIN_TOKEN`, and `SETTINGS_ENCRYPTION_KEY`.

### 2. Signatures

- `GET /api/llm-providers?enabled=<bool>&status=<status>`
- `POST /api/llm-providers`
- `PATCH /api/llm-providers/{provider_id}`
- `DELETE /api/llm-providers/{provider_id}`
- `POST /api/llm-providers/{provider_id}/test`
- `GET /api/llm-providers/{provider_id}/models`
- `POST /api/llm-providers/fetch-models`
- `GET /api/summary-profiles`
- `POST /api/summary-profiles`
- `PATCH /api/summary-profiles/{profile_id}`
- `DELETE /api/summary-profiles/{profile_id}`
- `POST /api/summary-profiles/{profile_id}/set-default`

### 3. Contracts

- All endpoints are mounted below `/api` and require `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`.
- `GET /api/llm-providers` returns a direct JSON array of providers, not an `{items}` envelope.
- Provider response must expose `secret: { configured: bool, updated_at: datetime | null }`, never `api_key` or encrypted secret values.
- Provider create requires `name`, `provider_type`, `api_key`, and `default_model`; it may also accept `models`.
- Provider responses include persisted `models: list[str]`; legacy or empty model lists fall back to `[default_model]`.
- Provider model IDs are trimmed non-empty strings. `default_model` must be present in `models`; invalid model lists return `400 validation_error`.
- Provider patch treats `api_key` as:
  - missing: no change
  - `null`: no change
  - empty string or whitespace-only string: no change
  - non-empty string: replace encrypted secret and reset validation status
- Provider patch with `models` replaces the stored model list.
- `GET /api/llm-providers/{id}/models` returns persisted provider models.
- `POST /api/llm-providers/fetch-models` may use a temporary request API key to fetch upstream models, but must not persist or audit the plaintext key.
- Provider test responses return UI-facing `success` and `detail` fields alongside safe diagnostic status fields.
- Provider delete is a hard delete only when the provider is unused. Reject with `409 conflict` when referenced by Summary Profiles, Summary Jobs, or Summary Results.
- `GET /api/summary-profiles` returns a direct JSON array of profiles, not an `{items}` envelope.
- Summary Profile response exposes flat provider fields: `llm_provider_id`, `llm_provider_name`, and `provider_type`.
- Summary Profile response includes `effective_model` and `uses_provider_default_model`.
- `model: null` means the profile uses its provider default model.
- Summary Profile delete is a hard delete only when unused and not default. Reject with `409 conflict` when default or referenced by Group Summary Settings, Summary Jobs, or Summary Results.

### 4. Validation & Error Matrix

- Missing or invalid auth -> `401 {"error": {"code": "unauthorized", "message": "认证失败"}}`.
- Unsupported provider type -> `400 validation_error`.
- Provider `timeout_seconds <= 0` -> `400 validation_error`.
- Provider `max_retries < 0` -> `400 validation_error`.
- Profile `temperature` outside `0..2` -> `400 validation_error`.
- Profile `max_output_tokens <= 0` -> `400 validation_error`.
- Missing provider/profile ID -> `404 not_found`.
- Provider/Profile referenced delete -> `409 conflict`.
- FastAPI request validation errors must use the redacted `request validation failed` response and must not echo request input.

### 5. Good/Base/Bad Cases

- Good: `PATCH /api/llm-providers/{id}` with `{"api_key": "new"}` encrypts and stores the new key, returns only `secret.configured`, and writes redacted audit.
- Good: `PATCH /api/llm-providers/{id}` with `{"models": ["gpt-4o-mini"], "default_model": "gpt-4o-mini"}` replaces the safe persisted model list.
- Good: `DELETE /api/summary-profiles/{id}` deletes an unused non-default profile and writes a redacted audit log.
- Base: `PATCH /api/llm-providers/{id}` with `{}` or blank `api_key` returns the provider without changing encrypted key material.
- Base: Anthropic model fetch may return a curated preset list when no reliable upstream list endpoint is supported.
- Bad: returning Pydantic/FastAPI default validation details for a malformed request that contains a secret-bearing field.
- Bad: soft-deleting or hiding referenced providers/profiles in this API; current policy is hard delete only when unused, otherwise `409 conflict`.

### 6. Tests Required

- Auth protection for read and write endpoints.
- Read responses do not contain LLM API key, bot token, admin token, or encryption key.
- Provider blank/null/missing `api_key` is a no-op.
- Provider non-empty `api_key` replaces encrypted value and audit remains redacted.
- Provider model list create/update/get/fetch behavior.
- Provider/Profile delete success and conflict behavior.
- Summary Profile default switching leaves exactly one `is_default = true`.
- Invalid provider/profile parameters return `validation_error`.
- Malformed request validation does not echo the secret-bearing input.

### 7. Wrong vs Correct

#### Wrong

```python
raise HTTPException(status_code=422, detail=exc.errors())
```

This can echo invalid request inputs, including `api_key` values.

#### Correct

```python
return api_error_response(
    status_code=400,
    code="validation_error",
    message="request validation failed",
)
```

Use service-layer validation for field-specific safe messages, and never include raw secret-bearing request values in API responses, logs, exceptions, or audit logs.

## Scenario: WebUI Dashboard, Groups, Summaries, And Private Relays

### 1. Scope / Trigger

- Trigger: changing display contracts for the rewritten React WebUI.
- Applies to `src/summary_relay_bot/web/routes/dashboard.py`, `groups.py`, `summaries.py`, `private_relays.py`, `audit_logs.py`, schemas in `src/summary_relay_bot/web/schemas.py`, and frontend types/client code under `web/src/api/`.
- Secret-bearing data remains forbidden in all management responses. Raw group message bodies must not be exposed.

### 2. Signatures

- `GET /api/dashboard`
- `GET /api/groups`
- `GET /api/groups/{group_id}`
- `PATCH /api/groups/{group_id}/summary-settings`
- `POST /api/groups/{group_id}/summary-jobs`
- `GET /api/groups/{group_id}/summary-jobs/{job_id}`
- `GET /api/summaries`
- `GET /api/private-relays`
- `GET /api/audit-logs`

### 3. Contracts

- Dashboard returns WebUI-ready chart and display fields:
  - `bot.telegram_identity`
  - `default_profile.provider_id`
  - `default_profile.provider_name`
  - `summary_24h.trend`
  - `summary_24h.group_distribution`
- Dashboard `recent_audit_logs` is a compact safe audit subset. It does not include `redacted_before` or `redacted_after`; callers that need payload comparison use `GET /api/audit-logs`.
- Audit log list responses keep `redacted_before` and `redacted_after` as JSON objects or `null`, not JSON-encoded strings.
- Group list/detail `effective_profile` includes display-ready `id`, `name`, `model`, and `provider`.
- `PATCH /api/groups/{group_id}/summary-settings` returns the full updated `GroupDetail`, not only the settings object.
- Summary job responses include `sequence_range`, `provider`, `profile_name`, `model`, and `result` so the WebUI does not need to reconstruct labels from internal IDs.
- Manual summary trigger returns `poll_url` pointing to `/api/groups/{group_id}/summary-jobs/{job_id}`. Do not add duplicate `/api/summary-jobs/{groupId}/{jobId}/poll` routes.
- `GET /api/summaries` returns generated historical summaries with group metadata, job metadata, provider/profile display fields, `content`, and cursor pagination. `content` comes from generated summary output, never raw source group messages.
- `GET /api/private-relays` is read-only and returns bounded private message previews, safe private-user metadata, reply-map metadata, delivery status fields, aggregate stats, and cursor pagination. It must not expose raw Telegram update payloads.
- Database IDs remain numeric in API data. Frontend controls that require string values stringify only at the component boundary.

### 4. Validation & Error Matrix

- Missing or invalid auth -> `401 {"error": {"code": "unauthorized", "message": "认证失败"}}`.
- Invalid cursor, limit, status, direction, or date filter -> `400 validation_error`.
- Missing group or summary job -> `404 not_found`.
- Manual summary conflict -> `409 conflict`.
- FastAPI request validation errors must use the redacted `request validation failed` response and must not echo request input.

### 5. Good/Base/Bad Cases

- Good: Dashboard uses `/api/system/reload-bot-runtime` for pending Bot runtime config and displays backend-provided trend/distribution data directly.
- Good: GroupDetail polls `/api/groups/{group_id}/summary-jobs/{job_id}` until the returned job reaches a terminal state.
- Good: Summaries exposes generated `summary_results.summary_text` as `content` without source message bodies.
- Good: PrivateRelays exposes bounded `text_preview` / `caption_preview` to the authenticated admin UI without raw update payloads.
- Base: nullable group titles, profile names, providers, and models are valid; clients should show fallback labels.
- Bad: a frontend mock server or mock fallback path becoming the normal WebUI API contract.
- Bad: converting audit payload objects to JSON strings in the backend or parsing them as strings in the frontend.

### 6. Tests Required

- Dashboard empty-state and populated-state tests including chart arrays, provider display fields, Telegram identity, and secret redaction.
- Group list/detail/settings/job tests covering display fields, auth, conflicts, and polling URL shape.
- Historical summaries tests covering content, filters, pagination, auth, and no raw message/secret leaks.
- Private relay tests covering previews, filters, pagination, stats, auth, and no raw update/secret leaks.
- Audit log tests covering JSON object payloads and redaction.
- Frontend typecheck and production build against the real backend contract.

## Scenario: WebUI Static Deployment

### 1. Scope / Trigger

- Trigger: changing FastAPI static mounting, SPA fallback, Docker image assembly, or WebUI bootstrap env.
- Applies to `src/summary_relay_bot/web/app.py`, `src/summary_relay_bot/web/static.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`, and deployment docs.
- Secret-bearing bootstrap env includes `WEBUI_ADMIN_TOKEN` and `SETTINGS_ENCRYPTION_KEY`.

### 2. Signatures

- `/api/*` with any supported HTTP method: routed only to existing authenticated API routers or an API 404 fallback.
- `GET /`: returns built React/Vite `index.html` when `web/dist/index.html` exists.
- `GET /groups/{id}` and other non-API extensionless paths: return `index.html` for SPA routing.
- `GET /assets/<file>` and other file-like paths: return the built file when it exists, otherwise 404.

### 3. Contracts

- Static mounting must be registered after `/api` routers so API routes keep their authentication and response semantics.
- SPA fallback must not handle `/api` or `/api/*`; missing API paths should remain API 404s, not frontend HTML.
- When the built `web/dist/index.html` exists, register an explicit `/api/{path:path}` fallback for common HTTP methods before the SPA catch-all. Without this, Starlette can treat a missing `POST /api/...` as `405 Method Not Allowed` because the GET/HEAD SPA catch-all matches the path.
- If `web/dist/index.html` is absent, static mounting is a no-op so backend tests and API-only development still run.
- Normal `web` dev/build scripts use Vite directly. `web/server.ts` is a mock/prototype artifact and must not be in the normal production build/start path.
- Docker build uses a Node stage for `npm ci` and `npm run build`, then copies only `web/dist` into the Python runtime image.
- The Python runtime image must not install or depend on Node/npm.
- `.dockerignore` must exclude local `web/node_modules/`, local `web/dist/`, and local data directories from the build context.

### 4. Validation & Error Matrix

- Missing or invalid `/api/*` auth -> existing `401 {"error": {"code": "unauthorized", "message": "认证失败"}}`.
- Missing `/api/*` path, including `POST /api/system/restart`, -> 404.
- Missing static asset with file extension -> 404.
- Missing SPA route without file extension -> `index.html`.
- Missing `web/dist/index.html` at runtime -> no static routes are mounted.

### 5. Good/Base/Bad Cases

- Good: refreshing `/groups/123` returns frontend HTML, and `GET /api/dashboard` without auth still returns the JSON 401.
- Base: running backend tests without a frontend build still creates the FastAPI app.
- Bad: a catch-all route returns `index.html` for `/api/dashboard`, bypassing API auth or changing API error shape.

### 6. Tests Required

- Smoke test for `/` returning built HTML.
- Smoke test for unauthenticated `/api/dashboard` returning the standard JSON 401.
- Smoke test that a missing non-GET `/api/*` path returns 404 when `web/dist` exists.
- Smoke test for an SPA child route returning the same `index.html`.
- Static checks for Dockerfile stages when Docker is unavailable: source paths exist, runtime stage has no Node/npm commands, and `.dockerignore` excludes local frontend/data artifacts.

### 7. Wrong vs Correct

#### Wrong

```python
app.mount("/", StaticFiles(directory="web/dist", html=True), name="webui")
```

This can let the frontend catch-all compete with `/api/*` paths and obscure API errors.

#### Correct

```python
app.include_router(api_router)
mount_webui_static(app)
```

Register API routes first, explicitly exclude `/api/*` from fallback, and return `index.html` only for non-file SPA routes.
