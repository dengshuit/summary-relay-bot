# Batch 04: Group / Summary Job / Audit API

## Goal

Continue the archived WebUI config center implementation and implement only Batch 04: Group / Summary Job / Audit API.

## Required References

- `AGENTS.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/prd.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/plan.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/batch-04-groups-jobs-audit-api.md`
- `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`
- `src/summary_relay_bot/db/models.py`
- `src/summary_relay_bot/db/repositories.py`
- `src/summary_relay_bot/services/runtime_config.py`
- `src/summary_relay_bot/services/summary_jobs.py`
- `src/summary_relay_bot/services/group_settings.py`
- `src/summary_relay_bot/services/secrets.py`
- `src/summary_relay_bot/web/`
- related `tests/`

## Scope

Implement only:

1. Read-only group list and group detail API.
2. Group summary settings update API. `summary_profile_id = null` means no bound profile; runtime uses default profile.
3. Manual summary job trigger API. It creates a manual job, returns `202`, and exposes polling status.
4. Backend conflict protection: active/running job in the same group returns `409 summary_job_conflict`.
5. Audit log read API with `entity_type`, `action`, time range, `limit`, and `cursor` filtering/pagination.
6. Redacted audit logs for `update_group_summary_settings` and `trigger_summary`.
7. Read APIs do not write audit logs.
8. API responses, audit before/after, logs, and exceptions must not leak secrets.
9. Tests covering group read list/detail, settings validation, `summary_profile_id = null`, active job conflict, manual job polling, audit filtering/pagination, auth protection, and redaction.

## Out of Scope

- No `POST /api/groups`; groups are still bot-discovered.
- No Redis/Celery/distributed worker.
- No LLM fallback.
- No summary cost statistics.
- No React/Vite frontend.
- No static frontend mounting.
- No `prototype/` changes.
- No multi-admin, RBAC, or session cookie.
- No Batch 05/06 work.

## Validation

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_web_groups_api.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_audit_logs_api.py tests/unit/test_summary_jobs.py -q
.venv/bin/python -m compileall -q src tests migrations
```
