# Telethon userbot WebUI authorization - Design

## Scope

This child adds a safe control-plane path for one enabled Telethon userbot account:

- dependency support for Telethon 1.x and async SOCKS proxy support
- backend service functions for userbot config and auth state
- a Telethon adapter boundary that can use real `TelegramClient` in production and fakes in tests
- FastAPI routes under `/api/userbot`
- a minimal WebUI page for configuration, status, code login, and 2FA completion

It does not implement group discovery, Telethon event handlers, message ingestion, summary scheduling, or notification delivery.

## Data Model Use

The schema-reset child already created the tables this task needs:

- `summary_userbots`
  - public metadata: `id`, `name`, `api_id`, `enabled`, `auth_status`, `runtime_status`, Telegram identity fields, lifecycle timestamps, last error fields
  - encrypted secrets: `api_hash_encrypted`, `phone_number_encrypted`, `session_encrypted`, `proxy_url_encrypted`
- `summary_userbot_auth_sessions`
  - encrypted `phone_code_hash_encrypted`
  - `status`, expiry, last error fields, timestamps

No new migration is planned for this child unless implementation discovers a schema contradiction. The first implementation enforces at most one enabled userbot in service code and relies on the existing partial unique index as the database backstop.

## Backend Service Contract

Create a dedicated userbot service module instead of extending the Bot API runtime-config service with Telethon-specific behavior.

Service-level concepts:

- `SummaryUserbotView`: safe response model for WebUI/API.
- `SummaryUserbotSecretState`: configured flags for `api_hash`, `phone_number`, `session`, and `proxy_url`; never plaintext or encrypted values.
- `UserbotRuntimeConfig`: decrypted runtime material for later children; `safe_dict()` and `__repr__()` must redact secrets.
- `UserbotAuthClient`: protocol/adapter for send-code, sign-in-with-code, sign-in-with-password, session export, and identity lookup.

Required operations:

- list/get the single current userbot view
- create userbot config
- patch userbot config
- request phone code
- submit phone code
- submit 2FA password
- load enabled authorized runtime config for later runtime children

Validation rules:

- `name` must be non-empty.
- `api_id` must be a positive integer.
- creating an enabled userbot while another enabled userbot exists returns `400 validation_error`.
- patching `api_hash`, `phone_number`, `proxy_url`, or `session` treats missing/null/blank values as no change; non-blank values replace the encrypted field.
- enabling an existing userbot disables other enabled userbots and sets their `runtime_status` to `disabled`.
- replacing `api_id`, `api_hash`, `phone_number`, `proxy_url`, or `session` clears auth attempt state as needed and marks the runtime no longer running.

Audit logs:

- audit rows may include safe booleans, status values, IDs, and redacted identity fields only.
- audit rows must not include `api_hash`, phone code, 2FA password, `StringSession`, encrypted secret blobs, admin token, bot token, or LLM API key.

## Telethon Adapter

Use a small adapter module to isolate Telethon imports and network calls.

Production adapter behavior:

- build `TelegramClient(StringSession(existing_or_empty), api_id, api_hash, proxy=...)`
- call `connect()` before auth actions and `disconnect()` in a `finally` block
- `send_code_request(phone)` returns a phone code hash
- `sign_in(phone=..., code=..., phone_code_hash=...)` returns identity when authorized
- when Telethon raises the 2FA-required exception, the service updates auth status to `password_required` without persisting the code or password
- `sign_in(password=...)` completes 2FA and exports the encrypted `StringSession` value

Testing behavior:

- tests inject fake clients through FastAPI app state or monkeypatch a factory
- no test calls Telegram or uses real account credentials
- fake clients return deterministic phone code hashes, session strings, and identity metadata

Proxy handling:

- the service stores proxy URL encrypted.
- the adapter parses only supported proxy URLs needed for Telethon construction.
- invalid proxy URLs return a safe validation error that does not echo credentials or host details.

## API Contract

All routes are mounted below `/api`, use the existing admin bearer-token dependency, and use the standard error envelope.

Endpoints:

- `GET /api/userbot`
  - returns `{ active: int | null, item: Userbot | null }`
- `POST /api/userbot`
  - create a config with `name`, `api_id`, `api_hash`, `phone_number`, optional `proxy_url`, optional `enabled`
- `PATCH /api/userbot`
  - update the existing config by `id`
- `POST /api/userbot/send-code`
  - request a Telegram phone code for the stored or provided phone/API credentials
- `POST /api/userbot/sign-in`
  - submit code for the latest active code session
- `POST /api/userbot/submit-password`
  - submit 2FA password for the latest password-required auth session

Safe response fields:

- ID, name, API ID, enabled
- `auth_status`, `runtime_status`
- Telegram identity metadata when authorized
- timestamps and safe `last_error_type` / `last_error_message`
- secret configured flags only

Forbidden response/log/audit fields:

- `api_hash`
- phone code
- 2FA password
- `StringSession`
- encrypted secret blobs
- raw phone number unless the response uses a redacted phone display field

## WebUI Contract

Add a minimal `Userbot` page and sidebar entry distinct from private relay Bot config.

The page should support:

- reading current userbot state
- creating/updating name, API ID, API hash replacement, phone number replacement, proxy replacement, and enabled flag
- sending phone code after config is saved
- submitting code
- submitting 2FA password only when backend reports `password_required`
- displaying auth/runtime status and safe error metadata

The page must not render a stored `api_hash`, phone code, password, session string, or encrypted secret. Secret inputs are replacement-only and clear after submit.

## Runtime Status Boundary

This child exposes persisted `runtime_status` and safe last error fields but does not start a long-running Telethon collector. The next child will add a summary userbot runtime manager that consumes the authorized runtime config and updates `runtime_status` to `starting/running/failed/disabled`.

For this child:

- newly created disabled configs report `runtime_status=disabled`
- enabled but not authorized configs report `runtime_status=stopped`
- successful authorization keeps `runtime_status=stopped` unless a later runtime manager is mounted

## Security And Failure Handling

- Request validation errors must use the existing redacted validation handler and must not echo request bodies.
- Service errors become safe `400 validation_error`, `404 not_found`, or conflict-style errors as appropriate.
- Telethon transient/auth errors are mapped to safe `auth_status=error` or auth-session failure metadata without logging secrets.
- The service stores phone code hash encrypted, expires auth sessions, and always uses the latest non-terminal auth session for code/password submission.

## Cross-Layer Data Flow

Create/update:

`WebUI form -> /api/userbot -> service validation/encryption -> summary_userbots -> safe response -> WebUI status`

Send code:

`WebUI action -> /api/userbot/send-code -> service decrypts credentials -> Telethon adapter -> encrypted auth session -> safe response`

Code sign-in:

`WebUI code -> /api/userbot/sign-in -> service decrypts phone code hash -> Telethon adapter -> encrypted session or password_required state -> safe response`

2FA:

`WebUI password -> /api/userbot/submit-password -> Telethon adapter -> encrypted session -> safe response`

Secrets are write-only at API/UI boundaries and plaintext exists only inside service/adapter local variables.
