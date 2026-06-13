# Implementation Plan

## Checklist

- [x] Add backend schema types for summary test task responses.
- [x] Add repository helper for latest group messages capped at 50 and returned chronologically.
- [x] Add `summary_test_tasks` service with bounded in-memory task registry and worker logic.
  - [x] Enforce maximum task count.
  - [x] Expire terminal tasks by TTL.
  - [x] Evict oldest terminal tasks before rejecting new active work.
- [x] Mount the task registry in `create_web_app` and add a dependency getter.
- [x] Add authenticated group routes for creating and polling summary test tasks.
- [x] Add focused backend tests:
  - [x] successful test task summarizes only latest 50 messages
  - [x] success does not advance `summary_state`
  - [x] success creates no `summary_jobs` / `summary_results`
  - [x] registry cleanup/limit behavior prevents unbounded growth
  - [x] failure returns safe error fields
  - [x] auth required
- [x] Add frontend API/types for summary test tasks.
- [x] Add `TaskProgressPanel` component with steps, indeterminate progress, success/error/cancel states, retry and result actions.
- [x] Update `GroupDetail.tsx`:
  - [x] call the test-summary endpoint
  - [x] poll the test task
  - [x] show progress panel in place of the existing top status banner
  - [x] open result dialog on success
  - [x] show error details and retry on failure
- [x] Update stale copy that says Web summary was delivered or pushed.

## Validation Commands

- `pytest tests/unit/test_web_summary_test_tasks_api.py`
- `pytest tests/unit/test_web_summary_jobs_api.py tests/unit/test_summary_jobs.py`
- `npm run lint` in `web/`
- `npm run build` in `web/`

Executed:

- `/tmp/summary-relay-bot-venv/bin/pytest tests/unit/test_web_summary_test_tasks_api.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_summary_jobs.py`
- `/tmp/summary-relay-bot-venv/bin/pytest tests/unit/test_web_groups_api.py tests/unit/test_web_summaries_api.py`
- `python3 -m compileall -q src tests/unit/test_web_summary_test_tasks_api.py`
- `npm run lint` in `web/`
- `npm run build` in `web/`

## Risky Files

- `src/summary_relay_bot/services/summary_jobs.py`: production summary behavior must remain unchanged unless a shared helper is extracted.
- `src/summary_relay_bot/web/routes/groups.py`: avoid changing existing production job polling response shapes.
- `web/src/views/GroupDetail.tsx`: preserve settings form behavior and existing active production job handling.

## Rollback Point

The feature can be rolled back by removing the new test-task routes/service and reverting `GroupDetail.tsx` to call `triggerGroupSummary`.
