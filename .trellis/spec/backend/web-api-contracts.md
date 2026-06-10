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
