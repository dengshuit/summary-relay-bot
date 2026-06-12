# Batch 06 Deploy Smoke Docs

## Status

Deprecated historical task.

This PRD described deployment and smoke-test work for the deprecated
React/Semi frontend. Do not use its static asset or Docker build assumptions as
current Web UI guidance.

The only still-useful historical constraints are:

- `/api/*` remains the backend API namespace.
- WebUI bootstrap env includes `DATABASE_URL`, `SETTINGS_ENCRYPTION_KEY`, and
  `WEBUI_ADMIN_TOKEN`.
- Secret values must remain encrypted at rest and redacted in API/logs/audit.
- Any current deployment plan must be validated against the current `web/`
  implementation rather than this archived batch.
