# Parent Completion Review

Date: 2026-06-13

All seven child tasks under `06-13-telethon-group-summary-refactor` are marked
completed. A main-session follow-up review was performed after the final child
task to avoid waiting for unavailable sub-agents.

Follow-up fixes from that review:

- Production WebUI group discovery refresh uses a real Telethon discovery
  provider instead of requiring test-only app state injection.
- Summary userbot startup performs one visible-group discovery scan and updates
  safe runtime status.
- Scheduled summary jobs are keyed by summary entity `group_id`, not raw
  Telegram `chat_id`, and enabled-group scheduling is scoped to the enabled
  userbot when one exists.
- Enabling a different userbot disables previously enabled summary entities for
  the old userbot.
- Chunked summary notification retry resumes from the first unsent chunk and
  records partial `sent_chunks` / `telegram_message_ids`.

Validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py tests/unit/test_web_groups_api.py tests/unit/test_userbot_auth_service.py tests/unit/test_scheduler.py tests/unit/test_main.py -q` passed: 36 tests.
- `.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/unit/test_summary_notifications.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q` passed: 19 tests.
- `.venv/bin/python -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py -q` passed: 33 tests.
- `.venv/bin/python -m pytest tests/integration/test_persistence.py tests/integration/test_group_collection.py tests/integration/test_web_dashboard.py -q` passed: 8 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.
- `git diff --check` passed.

Second follow-up from the parent completion audit:

- Added a fakeable summary userbot update collector boundary for Telethon
  `NewMessage`, `MessageEdited`, and `MessageDeleted` updates.
- The summary userbot runtime now starts at most one long-lived collector task
  after startup discovery, routes normalized update DTOs into the existing
  ingestion service, disconnects/cancels the collector on stop, and records a
  safe failed runtime status when the collector task fails.
- Added unit coverage proving startup discovery plus collector launch, disabled
  group ignore behavior, enabled-group message storage, edit/delete routing,
  duplicate collector prevention, collector failure status, stop cleanup, and
  Telethon event normalization without real Telegram calls.

Additional validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `.venv/bin/python -m pytest tests/unit/test_telegram_userbot.py tests/unit/test_userbot_runtime.py tests/unit/test_main.py -q` passed: 25 tests.
- `.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py tests/unit/test_web_groups_api.py tests/unit/test_userbot_auth_service.py tests/unit/test_scheduler.py tests/unit/test_main.py tests/unit/test_userbot_runtime.py tests/unit/test_telegram_userbot.py -q` passed: 45 tests.
- `.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/unit/test_summary_notifications.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q` passed: 19 tests.
- `.venv/bin/python -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py -q` passed: 33 tests.
- `.venv/bin/python -m pytest tests/integration/test_persistence.py tests/integration/test_group_collection.py tests/integration/test_web_dashboard.py -q` passed: 8 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.
- `git diff --check` passed.

Final completion audit:

- A full backend test run exposed one remaining compatibility-alias regression:
  optional `group_summary_settings()` returned a discovered `SummaryEntity`
  even when no settings were configured. The service now returns
  `settings.summary_settings` so unconfigured discovered groups correctly
  report no settings.
- `.trellis/spec/backend/database-guidelines.md` was updated with the concrete
  wrong/correct pattern for optional settings helpers using
  `GroupSummarySettings = SummaryEntity`.

Final validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `DATABASE_URL=sqlite+aiosqlite:////tmp/summary-relay-bot-final-audit.db .venv/bin/alembic upgrade head` passed on an empty SQLite database.
- `.venv/bin/python -m pytest -q` passed: 188 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.
- `git diff --check` passed.

Residual risks:

- The Telethon collector has been covered through fakeable boundaries and event
  normalization tests. Live Telegram behavior still needs a manual smoke test
  with a real authorized userbot because automated tests must not call Telegram.
- Vite still reports the existing chunk-size warning.
