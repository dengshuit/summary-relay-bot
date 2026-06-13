# Main-session Review

Date: 2026-06-13

Reviewed artifacts:

- `prd.md`
- `design.md`
- `implement.md`

Conclusion:

- Scope matches the parent child map: discovery, explicit enablement, normalized update-stream ingestion, edit/delete metadata, and no active historical backfill.
- The plan reuses existing summary-domain tables from the schema reset and does not require a migration.
- Network-facing Telethon behavior is isolated behind fakeable DTO/provider boundaries; tests should not use real Telegram.
- API changes are limited to group management refresh and preserve WebUI as the group-summary control plane.
- Out-of-scope work remains deferred: summary job persistence changes, notification delivery, and production runtime supervision.

## Implementation Review

Reviewed in main Codex session on 2026-06-13 because sub-agent review was unavailable.

Findings:

- Fixed `GET /api/groups` filtering after the schema reset: `GroupSummarySettings` is now a `SummaryEntity` compatibility alias, so the route must not self-join it. Filtering now uses direct `GroupChat.enabled` and `GroupChat.summary_profile_id` columns.
- Updated the group collection integration regression to assert the new schema contract directly: unsupported messages may create a discovered group row, but must leave summary settings unset and collection disabled.
- Added the WebUI refresh contract for `POST /api/groups/refresh-userbot` through frontend types, API client, and the Groups toolbar action.

Validation:

- `.venv/bin/python -m compileall -q src tests migrations` passed.
- `.venv/bin/python -m pytest tests/unit/test_userbot_ingestion_service.py -q` passed: 6 tests.
- `.venv/bin/python -m pytest tests/unit/test_web_groups_api.py tests/unit/test_web_summary_jobs_api.py -q` passed: 8 tests.
- `.venv/bin/python -m pytest tests/unit/test_summary_jobs.py tests/integration/test_group_collection.py -q` passed: 6 tests.
- `npm run lint` in `web/` passed.
- `npm run build` in `web/` passed with the existing Vite chunk-size warning.
