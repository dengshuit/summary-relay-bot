# Batch 05 Frontend App

## Goal

Initialize the real React + TypeScript + Vite WebUI and implement the Batch 05 pages against the existing `/api/*` management endpoints from completed Batches 01-04.

## What I already know

- User explicitly scoped this task to Batch 05 only.
- `prototype/` is visual and interaction reference only and must not be modified.
- Existing backend API lives under `src/summary_relay_bot/web/` and is authenticated with `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`.
- Existing API groups: `/api/dashboard`, `/api/bot`, `/api/llm-providers`, `/api/summary-profiles`, `/api/groups`, `/api/audit-logs`.
- Manual summary trigger is `POST /api/groups/{id}/summary-jobs`, returns HTTP 202 with `poll_url`, then `GET poll_url` until a terminal job status.
- Secret response shape is `secret: { configured, updated_at }`; API responses must not expose bot token, LLM API key, admin token, or encryption key.

## Requirements

- Add `web/` frontend project with React, TypeScript, Vite, Semi Design, Semi Icons, and React Router.
- Implement token login page; store token in `sessionStorage`; send `Authorization: Bearer <token>` on API requests.
- On authentication failure, clear the stored token and return to login or show `认证失败` without token details.
- Implement AppShell, navigation, and routes: Dashboard / Bot / 摘要引擎 / 群组 / 审计日志.
- Implement pages: Bot, LLM Provider, Summary Profile, Groups, Group Detail, Audit Logs, and Dashboard.
- Use existing backend APIs; do not mock existing interfaces.
- Secret fields support replacement only. Leave blank to omit the secret field from update requests.
- Bot token and owner id changes show restart semantics.
- Default profile switching uses a confirmation step.
- Manual summary trigger handles 202 + `poll_url` polling and 409 active-job conflict.
- Add minimal frontend verification scripts; at least `typecheck` and `build`.

## Out of Scope

- Do not modify `prototype/`.
- Do not implement backend APIs.
- Do not mount built frontend static assets into FastAPI.
- Do not implement Redis, Celery, distributed workers, LLM fallback, summary cost statistics, multi-admin, RBAC, session cookies, or Batch 06 deployment smoke.

## Acceptance Criteria

- [ ] `web/` contains a buildable React + TypeScript + Vite app.
- [ ] Login stores token in `sessionStorage` and API calls use bearer auth.
- [ ] Navigation contains exactly Dashboard / Bot / 摘要引擎 / 群组 / 审计日志.
- [ ] Engine page has LLM Provider / Summary Profile tabs.
- [ ] Bot, Provider, Profile, Groups, Group Detail, Audit Logs, and Dashboard pages call real API paths.
- [ ] Secret inputs never render or log plaintext secrets; blank values are omitted from update payloads.
- [ ] Manual summary trigger polls the returned `poll_url`.
- [ ] Authentication failures do not expose token details.
- [ ] `npm run typecheck` and `npm run build` pass in `web/`.

## Definition of Done

- Frontend project files are limited to this batch.
- Minimal verification scripts pass.
- No secret values are introduced in source, snapshots, logs, or test fixtures.
- Batch 06 static mounting/deployment work is not implemented.

## Technical Notes

- Required reading:
  - `AGENTS.md`
  - `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/prd.md`
  - `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/plan.md`
  - `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/batch-05-frontend-app.md`
  - `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`
  - `src/summary_relay_bot/web/`
- Relevant spec files read:
  - `.trellis/spec/guides/index.md`
  - `.trellis/spec/guides/cross-layer-thinking-guide.md`
  - `.trellis/spec/guides/code-reuse-thinking-guide.md`
  - `.trellis/spec/backend/index.md`
  - `.trellis/spec/backend/web-api-contracts.md`
  - `.trellis/spec/backend/quality-guidelines.md`
  - `.trellis/spec/backend/directory-structure.md`
