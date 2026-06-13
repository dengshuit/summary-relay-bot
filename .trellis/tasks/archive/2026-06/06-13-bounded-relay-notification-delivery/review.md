# Main-session Review

Date: 2026-06-13

Reviewed artifacts:

- `prd.md`
- `design.md`
- `implement.md`

Conclusion:

- Scope matches the parent child map: persisted summary results now schedule
  bounded notification delivery through the private relay bot when runtime
  resources are available.
- Summary job success remains independent of notification success. Delivery
  failures are recorded in `summary_delivery_attempts` and do not roll back
  summary results or cursors.
- Delivery is bounded by a dispatcher semaphore, max three attempts, and a
  per-attempt timeout.
- Web/API summary responses expose safe delivery metadata without raw owner ids,
  bot tokens, or source group messages.

Findings:

- Added deterministic text chunking to preserve full summary content across
  Telegram message-size limits.
- Runtime dependency resolution prefers the live Telegram runtime resources for
  notification dispatch; if unavailable, delivery is recorded as skipped instead
  of failing the summary job.

Validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `.venv/bin/python -m pytest tests/unit/test_summary_notifications.py tests/unit/test_summary_jobs.py -q` passed: 12 tests.
- `.venv/bin/python -m pytest tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q` passed: 6 tests.
- `.venv/bin/python -m pytest tests/unit/test_web_groups_api.py tests/unit/test_runtime_config.py -q` passed: 14 tests.
- `.venv/bin/python -m pytest tests/unit/test_main.py tests/unit/test_web_bot_api.py -q` passed: 32 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.
