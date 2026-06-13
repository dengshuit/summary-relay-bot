# Summary job persistence refactor - Design

## Scope

This child makes production summary jobs persist generated results and advance
the summary cursor independently of Telegram notification delivery.

It covers:

- WebUI-triggered manual summary jobs
- scheduled summary jobs for enabled groups
- one shared summary generation/persistence path with `manual` and `scheduled`
  trigger types
- existing LLM Provider and Summary Profile runtime configuration
- `summary_results` persistence before any notification work
- cursor advancement after result persistence
- WebUI-visible job/result/error/sequence state

It does not implement bounded private relay notification delivery. That remains
owned by `06-13-bounded-relay-notification-delivery`.

## Current State

The repository already has summary-domain tables from the schema reset:

- `summary_entities`
- `summary_messages`
- `summary_states`
- `summary_jobs`
- `summary_results`
- `summary_delivery_attempts`

The WebUI manual trigger already creates a pending `SummaryJob` through
`POST /api/groups/{group_id}/summary-jobs` and schedules
`run_web_manual_summary_job`.

The old bot-command/scheduler path still calls `run_summary_for_group`, which
requires an aiogram `Bot` and attempts Telegram delivery before creating the
result and advancing the cursor. That ordering conflicts with the parent PRD.

## Target Pipeline

Both manual and scheduled production jobs should use the same internal pipeline:

1. Ensure `SummaryState` exists for the group.
2. Create or claim one active `SummaryJob`.
3. Load the effective `SummaryProfileRuntimeConfig`.
4. Read normalized `SummaryMessage` rows with `id > starting_sequence`.
5. If no messages exist, mark the job `succeeded` with the unchanged cutoff.
6. Generate the summary with `PrivacyAwareSummaryClient`.
7. Create `SummaryResult` with provider/profile/model/prompt metadata and the
   exact interval sequence bounds.
8. Advance `SummaryState.last_summary_sequence` from the job starting sequence
   to the cutoff sequence.
9. Mark the job `succeeded`.

If runtime config or LLM generation fails, mark the job failed and leave the
cursor unchanged. If the cursor changed before advancement, mark the job failed
with `stale_cursor`; the generated result may exist for audit/history, but the
job is not successful and the cursor is not advanced.

## Interfaces

Keep public API shape stable:

- `POST /api/groups/{group_id}/summary-jobs` returns `202` and a pending job.
- `GET /api/groups/{group_id}/summary-jobs/{job_id}` returns status, provider,
  profile, model, sequence range, and result metadata.
- `GET /api/summaries` returns historical summary content from
  `summary_results.summary_text`, never source message bodies.

Service-level shape:

- Keep `create_manual_summary_job` for WebUI pending job creation.
- Keep `run_web_manual_summary_job` as the async executor for pending WebUI
  jobs.
- Keep `run_scheduled_summary` as scheduler entrypoint, but make it call the
  same generation/persistence core.
- Keep `run_summary_for_group` for compatibility with existing tests/callers,
  but remove Telegram delivery as a success prerequisite in this child.

The aiogram `Bot`, `owner_id`, and `SummaryReloadGate` parameters may remain on
compatibility functions until child 6 replaces notification delivery. This child
must not depend on Bot delivery success.

## Data Semantics

- The summary sequence is `SummaryMessage.id`, not Telegram message id.
- Summary input uses normalized `summary_content` from `summary_messages`.
- Deleted messages that remain after the current cursor are not retracted from
  already persisted results. Current repository behavior may include them unless
  a later child defines delete filtering.
- Edits after summarization are tracked by ingestion and do not rewrite
  historical `SummaryResult` rows.
- `SummaryResult.interval_start_sequence` is the previous cursor.
- `SummaryResult.interval_end_sequence` is the max summarized message id.
- `SummaryJob.cutoff_sequence` matches the interval end for generated jobs.

## Compatibility

No migration is expected. The schema already contains the target tables and
compatibility properties for older test/helper names.

Existing WebUI response shapes should not change. Tests should continue to
assert that raw group message text, LLM API keys, bot tokens, admin tokens, and
encryption keys are not returned by summary job or summary history APIs.

## Rollback

This is a service-layer refactor. Rollback is limited to reverting
`summary_jobs.py` and any tests updated for the new cursor/result semantics.
No schema rollback is involved.
