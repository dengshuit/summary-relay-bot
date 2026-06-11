# Batch 06 Deploy Smoke Docs

## Goal

Implement only Batch 06 from the archived WebUI configuration center plan: single-process deployment, static WebUI mounting, minimal smoke tests, Docker multi-stage build, and documentation updates.

## Source Requirements

- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/prd.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/plan.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/batch-06-deploy-smoke-docs.md`
- `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`

## Scope

- Mount React/Vite `web/dist` static assets in FastAPI.
- Keep `/api/*` routed to existing Web API behavior.
- Return the SPA `index.html` for non-API child routes such as `/groups/:id`.
- Convert `Dockerfile` to a multi-stage build where Node builds `web/dist` and the Python runtime image does not depend on Node.
- Update `README.md`, `README.zh-CN.md`, and `docs/operations/telegram-summary-relay-bot.md`.
- Document bootstrap env: `DATABASE_URL`, `SETTINGS_ENCRYPTION_KEY`, `WEBUI_ADMIN_TOKEN`, `WEBUI_HOST`, `WEBUI_PORT`.
- Document secret boundary: encrypted at rest, redacted in API/logs/audit, WebUI replacement-only and never plaintext viewing.
- Document `needs_restart`: bot token, owner id, and enabled bot changes require restart; Provider/Profile/Group settings do not.
- Add minimal smoke coverage for static page access, API authentication, and SPA child-route fallback.

## Out of Scope

- No `prototype/` changes.
- No new backend business API.
- No semantic changes to Batch 01-05 APIs.
- No Nginx, HTTPS production scheme, separate frontend service, multi-admin, RBAC, session cookie, Redis/Celery/distributed worker, LLM fallback, summary cost tracking, or key rotation.

## Validation

- `python3 -m compileall -q src tests migrations`
- `cd web && npm run typecheck && npm run build`
- Minimal pytest or e2e command covering static mount/smoke behavior.
- `docker compose build bot` if the environment allows.
