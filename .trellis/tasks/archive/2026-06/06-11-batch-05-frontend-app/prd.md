# Batch 05 Frontend App

## Status

Deprecated historical task.

This PRD described the deprecated first React/Semi WebUI implementation. It
must not be used as current `web/` implementation guidance.

Keep only these historical backend/API constraints in mind when useful:

- Authenticated API calls use `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`.
- Secret responses expose configured metadata only, not plaintext secret values.
- Secret updates are replacement-only; blank values must not clear existing
  secrets.
- Manual summary trigger uses the backend summary job flow and must handle an
  active-job conflict.

Current Web UI implementation work should use the current `web/` sources and
current API-contract planning, not this archived frontend scaffold.
