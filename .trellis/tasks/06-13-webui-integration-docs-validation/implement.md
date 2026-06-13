# WebUI integration docs and validation - Implementation Plan

## Ordered Steps

1. WebUI delivery status
   - Add compact delivery status rendering for historical summaries.
   - Add compact delivery status rendering for group detail production job
     result/poll state if the page already shows job status.
   - Keep display metadata safe; do not show raw owner chat id.

2. Documentation
   - Update `README.md` and `README.zh-CN.md` for Telethon setup, userbot
     secret risks, proxy dependency, schema reset, no active backfill, and
     summary result/cursor/delivery ordering.
   - Remove stale statements that cursor advancement depends on Telegram
     delivery success.

3. Cross-child tests
   - Run backend suites for userbot auth, ingestion, summary jobs,
     notifications, Web APIs, private relay, runtime config, and persistence.
   - Run frontend typecheck/build.

4. Task status
   - Record final review and mark child complete when validation passes.
   - Update parent task progress after all children are complete.

## Validation Commands

Run from the repo root:

```bash
.venv/bin/python -m compileall -q src tests migrations
.venv/bin/python -m pytest tests/unit/test_userbot_auth_service.py tests/unit/test_web_userbot_api.py -q
.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py tests/unit/test_web_groups_api.py -q
.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/unit/test_summary_notifications.py -q
.venv/bin/python -m pytest tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q
.venv/bin/python -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py -q
.venv/bin/python -m pytest tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py -q
.venv/bin/python -m pytest tests/integration/test_persistence.py tests/integration/test_group_collection.py tests/integration/test_web_dashboard.py -q
cd web && npm run lint
cd web && npm run build
```

## Review Checklist

- WebUI surfaces distinct Bot and Userbot control planes.
- Group discovery, enablement, manual summary, summary result inspection, and
  delivery metadata are visible from WebUI.
- Docs match implemented summary/delivery ordering.
- Docs do not promise historical backfill.
- Validation passes with only known non-blocking build warnings.
