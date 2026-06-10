# Batch 02 Bot Config API

## Goal

Implement only Batch 02 from the archived WebUI config center plan: Bot configuration API.

## Source Requirements

- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/prd.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/plan.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/batch-02-bot-config-api.md`
- `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`

## Scope

- Implement read-only Bot instance API.
- Implement minimal Bot instance update API for `name`, `owner_id`, `enabled`, and bot token replacement.
- Secret field semantics: missing, `null`, empty string, and whitespace-only string mean no change; non-empty string replaces the secret.
- Never expose bot token in API responses, logs, exceptions, or audit logs.
- Mark `needs_restart=true` when bot token or `owner_id` changes.
- Enforce at the backend that only one bot can be enabled at a time.
- Write redacted audit logs for mutating APIs.
- Add tests covering read redaction, empty secret no-op, replacement no leak, restart markers, enabled mutual exclusion, and auth protection.
- Run related pytest and compileall.

## Out of Scope

- Provider/Profile/Group/Audit APIs.
- React/Vite frontend.
- Static frontend mounting.
- `prototype/` changes.
- Multi-admin, RBAC, session cookies.
- Online Bot token switching, LLM fallback, or cost tracking.

## Acceptance Criteria

- `GET /api/bot` returns redacted Bot data and no secret plaintext.
- `PATCH /api/bot` respects no-op secret empty semantics.
- Secret replacement encrypts stored token and audit output stays redacted.
- `owner_id` or token change marks `needs_restart`.
- Enabling a bot disables other enabled bots at the backend.
- All `/api/bot*` endpoints require existing Web API token auth.
- Related tests and compileall pass.
