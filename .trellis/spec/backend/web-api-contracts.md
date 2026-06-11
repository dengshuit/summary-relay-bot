# Web API Contracts

## Scenario: LLM Provider / Summary Profile Management API

### 1. Scope / Trigger

- Trigger: adding or changing `/api/*` management endpoints.
- Applies to FastAPI routes under `src/summary_relay_bot/web/routes/`, schemas in `src/summary_relay_bot/web/schemas.py`, and business rules in `src/summary_relay_bot/services/runtime_config.py`.
- Secret-bearing fields include Bot token, LLM API key, `WEBUI_ADMIN_TOKEN`, and `SETTINGS_ENCRYPTION_KEY`.

### 2. Signatures

- `GET /api/llm-providers?enabled=<bool>&status=<status>`
- `POST /api/llm-providers`
- `PATCH /api/llm-providers/{provider_id}`
- `POST /api/llm-providers/{provider_id}/test`
- `GET /api/summary-profiles`
- `POST /api/summary-profiles`
- `PATCH /api/summary-profiles/{profile_id}`
- `POST /api/summary-profiles/{profile_id}/set-default`

### 3. Contracts

- All endpoints are mounted below `/api` and require `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`.
- Provider response must expose `secret: { configured: bool, updated_at: datetime | null }`, never `api_key` or encrypted secret values.
- Provider create requires `name`, `provider_type`, `api_key`, and `default_model`.
- Provider patch treats `api_key` as:
  - missing: no change
  - `null`: no change
  - empty string or whitespace-only string: no change
  - non-empty string: replace encrypted secret and reset validation status
- Summary Profile response includes provider summary, `effective_model`, and `uses_provider_default_model`.
- `model: null` means the profile uses its provider default model.

### 4. Validation & Error Matrix

- Missing or invalid auth -> `401 {"error": {"code": "unauthorized", "message": "认证失败"}}`.
- Unsupported provider type -> `400 validation_error`.
- Provider `timeout_seconds <= 0` -> `400 validation_error`.
- Provider `max_retries < 0` -> `400 validation_error`.
- Profile `temperature` outside `0..2` -> `400 validation_error`.
- Profile `max_output_tokens <= 0` -> `400 validation_error`.
- Missing provider/profile ID -> `404 not_found`.
- FastAPI request validation errors must use the redacted `request validation failed` response and must not echo request input.

### 5. Good/Base/Bad Cases

- Good: `PATCH /api/llm-providers/{id}` with `{"api_key": "new"}` encrypts and stores the new key, returns only `secret.configured`, and writes redacted audit.
- Base: `PATCH /api/llm-providers/{id}` with `{}` or blank `api_key` returns the provider without changing encrypted key material.
- Bad: returning Pydantic/FastAPI default validation details for a malformed request that contains a secret-bearing field.

### 6. Tests Required

- Auth protection for read and write endpoints.
- Read responses do not contain LLM API key, bot token, admin token, or encryption key.
- Provider blank/null/missing `api_key` is a no-op.
- Provider non-empty `api_key` replaces encrypted value and audit remains redacted.
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

## Scenario: WebUI Static Deployment

### 1. Scope / Trigger

- Trigger: changing FastAPI static mounting, SPA fallback, Docker image assembly, or WebUI bootstrap env.
- Applies to `src/summary_relay_bot/web/app.py`, `src/summary_relay_bot/web/static.py`, `Dockerfile`, `docker-compose.yml`, `.env.example`, and deployment docs.
- Secret-bearing bootstrap env includes `WEBUI_ADMIN_TOKEN` and `SETTINGS_ENCRYPTION_KEY`.

### 2. Signatures

- `GET /api/*` and other `/api/*` methods: routed only to existing authenticated API routers.
- `GET /`: returns built React/Vite `index.html` when `web/dist/index.html` exists.
- `GET /groups/{id}` and other non-API extensionless paths: return `index.html` for SPA routing.
- `GET /assets/<file>` and other file-like paths: return the built file when it exists, otherwise 404.

### 3. Contracts

- Static mounting must be registered after `/api` routers so API routes keep their authentication and response semantics.
- SPA fallback must not handle `/api` or `/api/*`; missing API paths should remain API 404s, not frontend HTML.
- If `web/dist/index.html` is absent, static mounting is a no-op so backend tests and API-only development still run.
- Docker build uses a Node stage for `npm ci` and `npm run build`, then copies only `web/dist` into the Python runtime image.
- The Python runtime image must not install or depend on Node/npm.
- `.dockerignore` must exclude local `web/node_modules/`, local `web/dist/`, and local data directories from the build context.

### 4. Validation & Error Matrix

- Missing or invalid `/api/*` auth -> existing `401 {"error": {"code": "unauthorized", "message": "认证失败"}}`.
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
