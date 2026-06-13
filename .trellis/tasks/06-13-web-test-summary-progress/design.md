# Design

## Architecture

Introduce a separate Web test-summary path instead of reusing production `summary_jobs`.

- Production summaries remain backed by `summary_jobs`, `summary_results`, `summary_state`, and Telegram delivery.
- Web test summaries use an in-process async task registry mounted on `FastAPI.app.state`.
- The registry exposes short-lived task status for polling and stores generated summary text only in memory.
- The registry has bounded retention: a maximum task count and TTL-based cleanup for terminal tasks.
- The WebUI group detail page calls the new test-summary endpoint and renders the task through a reusable progress panel.

## Backend Contract

Add routes under the existing authenticated `/api/groups` router:

- `POST /api/groups/{group_id}/summary-test-tasks`
  - Creates an ephemeral test task.
  - Returns `202` with `{ task, poll_url }`.
- `GET /api/groups/{group_id}/summary-test-tasks/{task_id}`
  - Returns current task state and result/error fields.
- Optional if implementation stays small: `POST /api/groups/{group_id}/summary-test-tasks/{task_id}/cancel`
  - Cancels a pending/running in-memory task and returns the canceled state.

Task schema fields:

- `id: str`
- `group_id: int`
- `chat_id: int`
- `status: pending | running | succeeded | failed | canceled`
- `step: submitted | queued | running | generating | completed`
- `message_count: int | null`
- `sequence_range: str | null`
- `summary_text: str | null`
- `error_type: str | null`
- `error_message: str | null`
- `created_at`, `started_at`, `finished_at`

Registry limits:

- Maximum tasks: 5.
- Terminal task retention TTL: 30 minutes.
- Before accepting a new task, the registry removes expired terminal tasks.
- If the registry is still full, it evicts oldest terminal tasks first.
- If all entries are active and the registry remains full, task creation returns a safe `409 summary_test_task_busy` response.

## Data Flow

1. Frontend creates a test task.
2. Backend validates group existence and records an in-memory task with status `pending`.
3. Backend schedules an asyncio task.
4. Worker re-fetches the group, loads the effective runtime summary config, and fetches the latest 50 `GroupMessage` rows for that group.
5. Messages are re-ordered ascending by internal sequence before sending to the existing privacy-aware summary client.
6. Worker updates the in-memory task with result text or error metadata.
7. Frontend polls until terminal state.
8. On success, frontend opens the summary result dialog. On failure, frontend keeps the progress panel with error and retry.

## Persistence And Cursor Semantics

The test path must not call:

- `create_pending_manual_summary_job`
- `create_running_summary_job`
- `mark_summary_job_running`
- `create_summary_result`
- `advance_summary_cursor_if_current`
- `bot.send_message`

The test path may read:

- `GroupChat`
- latest `GroupMessage` rows
- effective runtime summary config and encrypted LLM provider key through existing services

## Frontend Design

Build a reusable `TaskProgressPanel` component in `web/src/components`.

Visual direction:

- Work-focused admin card, compact and consistent with the existing group detail page.
- Muted neutral base with blue/green/red status accents, avoiding a one-hue purple/blue screen.
- Step rows have stable icon cells to avoid layout shift.
- Indeterminate progress bar is a narrow animated rail inside the card.
- Result dialog is a functional panel/modal with readable summary text and metadata, not a fullscreen loading state.

The existing top warning banner in `GroupDetail.tsx` is replaced by this component.

## Compatibility

- Existing `GET /api/groups/{group_id}/summary-jobs/{job_id}` remains available for production job polling.
- Existing scheduled summary jobs and historical summary APIs remain unchanged.
- Frontend no longer uses `POST /api/groups/{group_id}/summary-jobs` for the group-detail button.

## Risks And Trade-offs

- In-memory task state satisfies "no history records" but is not durable across process restart.
- Bounded in-memory retention means old test results disappear from the UI after the retention window.
- If the deployment runs multiple Web API workers, polling must hit the same worker unless a future shared task store is added.
- Test tasks still call the LLM provider, so they consume provider quota even though they do not affect production cursors.
