# Main-session Review

Date: 2026-06-13

Reviewed artifacts:

- `prd.md`
- `design.md`
- `implement.md`

Conclusion:

- WebUI now surfaces summary notification delivery state in historical summaries
  and group detail status.
- Documentation now matches the refactored architecture: Bot API private relay
  is separate from Telethon userbot collection, development schema reset does
  not preserve old data, userbot sessions are secret material, first-version
  collection has no active historical backfill, and notification delivery no
  longer controls summary cursor success.
- Final cross-child validation passed.

Validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `.venv/bin/python -m pytest tests/unit/test_userbot_auth_service.py tests/unit/test_web_userbot_api.py -q` passed: 11 tests.
- `.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py tests/unit/test_web_groups_api.py -q` passed: 11 tests.
- `.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/unit/test_summary_notifications.py -q` passed: 12 tests.
- `.venv/bin/python -m pytest tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q` passed: 6 tests.
- `.venv/bin/python -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py -q` passed: 7 tests.
- `.venv/bin/python -m pytest tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py -q` passed: 26 tests.
- `.venv/bin/python -m pytest tests/integration/test_persistence.py tests/integration/test_group_collection.py tests/integration/test_web_dashboard.py -q` passed: 8 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.

## Main-session Follow-up Review

Date: 2026-06-13

The user requested main-session review instead of waiting for sub-agents. The
review found and fixed three integration gaps:

- Production WebUI group refresh now has a real Telethon dialog discovery
  provider, and application startup runs one summary userbot discovery scan.
- Scheduled summaries now use `group_id`-scoped jobs and enabled-userbot
  filtering so stale groups from a disabled userbot do not collide by raw
  Telegram `chat_id`.
- Summary notification retries now resume after already-sent chunks instead of
  duplicating successful prefix chunks.

Additional validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py tests/unit/test_web_groups_api.py tests/unit/test_userbot_auth_service.py tests/unit/test_scheduler.py tests/unit/test_main.py -q` passed: 36 tests.
- `.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/unit/test_summary_notifications.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q` passed: 19 tests.
- `.venv/bin/python -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py -q` passed: 33 tests.
- `.venv/bin/python -m pytest tests/integration/test_persistence.py tests/integration/test_group_collection.py tests/integration/test_web_dashboard.py -q` passed: 8 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.
- `git diff --check` passed.
