# Telethon userbot WebUI authorization - Implementation Plan

## Ordered Steps

1. Dependency and contracts
   - Add Telethon 1.x and async SOCKS proxy dependency support.
   - Add backend Pydantic schemas for safe userbot responses and auth requests.
   - Add frontend TypeScript types and API client methods for `/api/userbot`.

2. Service and adapter
   - Create a Telethon adapter module with an injectable client/factory boundary.
   - Create a userbot config/auth service that owns validation, encryption, redaction, audit logs, one-enabled-userbot enforcement, and runtime config loading.
   - Keep plaintext secrets out of return values, logs, exceptions, and audit payloads.

3. API routes
   - Add `src/summary_relay_bot/web/routes/userbot.py`.
   - Mount the router in `web/app.py`.
   - Add dependency plumbing for an injectable Telethon client factory if needed for tests.
   - Map service errors to safe API error envelopes.

4. WebUI
   - Add a minimal `web/src/views/Userbot.tsx` page.
   - Add sidebar navigation and app route for distinct userbot configuration.
   - Implement replacement-only secret fields and code/password auth actions.
   - Display only safe status, identity metadata, configured flags, and safe errors.

5. Tests
   - Add focused unit tests for service config validation, encryption/redaction, auth success, 2FA required/completion, auth failures, expired/missing auth session, and one-enabled-userbot enforcement.
   - Add API tests for auth protection, safe response shape, request validation redaction, successful auth, 2FA flow, and secret non-leakage.
   - Run existing bot/LLM/API tests that enforce secret redaction and ensure private relay remains independent.
   - Run frontend type/build checks if WebUI files changed.

6. Task status
   - Update this child task status/notes after all validation commands pass.
   - Do not start `06-13-telethon-group-discovery-ingestion` until this child passes its validation.

## Review Checklist

- Parent requirements are preserved: one process, one DB, WebUI control plane, private relay independent from userbot.
- No implementation path requires a real Telegram account during tests.
- No API response, audit row, exception, or log contains `api_hash`, phone code, 2FA password, `StringSession`, bot token, LLM key, admin token, or encryption key.
- Runtime status is visible, but long-running collection remains out of scope for this child.
- The frontend does not display in-app instructional copy about secrets beyond normal field labels/status; docs coverage can be completed in the final docs child.

## Validation Commands

Run from the repo root:

```bash
.venv/bin/python -m compileall -q src tests migrations
.venv/bin/python -m pytest tests/unit/test_userbot_auth_service.py -q
.venv/bin/python -m pytest tests/unit/test_web_userbot_api.py -q
.venv/bin/python -m pytest tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py -q
.venv/bin/python -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py -q
cd web && npm run lint
cd web && npm run build
```

If dependency installation is needed before running validation, use the project virtualenv and do not use real Telegram credentials.

## Rollback Points

- If Telethon import/dependency causes unrelated runtime imports to fail, isolate imports further inside the adapter.
- If API tests find secret echoing through FastAPI validation, move the field-specific validation out of Pydantic default error paths and rely on the existing redacted request validation handler.
- If WebUI work grows beyond auth/config, stop at the minimal route/page and leave group management integration to later children.
