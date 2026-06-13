# Telethon group discovery and ingestion - Implementation Plan

## Ordered Steps

1. Contracts and service
   - Add summary userbot ingestion DTOs and service functions.
   - Reuse existing `SummaryEntity`, `SummaryMessage`, and `SummaryState` tables.
   - Keep service fakeable and free of Telegram network calls.

2. Telethon boundary
   - Add small adapter helpers for dialog/event normalization where needed.
   - Do not start real Telegram clients in tests.
   - Do not call historical APIs such as `iter_messages` / `get_messages`.

3. API
   - Add `POST /api/groups/refresh-userbot`.
   - Wire injectable dialog discovery provider through app state/deps.
   - Map missing authorized userbot to safe `409 conflict`.

4. WebUI
   - Add a refresh action to the Groups view if the existing UI has a natural control location.
   - Keep group enablement on existing group summary settings controls.
   - Avoid exposing raw message text beyond existing summary-domain UI contracts.

5. Tests
   - Add focused service tests for discovery/new/edit/delete ingestion.
   - Add focused API tests for refresh action.
   - Run existing group and summary API tests for regressions.

6. Task status
   - Mark this child complete only after targeted validation passes.

## Validation Commands

Run from the repo root:

```bash
.venv/bin/python -m compileall -q src tests migrations
.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py -q
.venv/bin/python -m pytest tests/unit/test_web_groups_api.py tests/unit/test_web_summary_jobs_api.py -q
.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/integration/test_group_collection.py -q
cd web && npm run lint
cd web && npm run build
```

## Review Checklist

- No real Telegram calls in tests.
- No active historical backfill is introduced.
- Disabled groups do not store messages.
- Broadcast channels are not collected/summarized in this child.
- Full raw Telethon payloads are not persisted.
- Existing WebUI group management response shapes remain compatible.
