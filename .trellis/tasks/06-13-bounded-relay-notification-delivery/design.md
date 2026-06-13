# Bounded relay notification delivery - Design

## Scope

This child adds bounded notification delivery for already persisted
`SummaryResult` rows through the configured private relay bot.

It covers:

- scheduling notification after successful summary result persistence
- sending the full summary text to the owner through the private relay bot
- splitting long notifications into ordered Telegram-safe chunks
- at most three total attempts: initial attempt plus two retries
- one-minute timeout per attempt
- bounded async concurrency inside one application process
- recording delivery status and metadata in `summary_delivery_attempts`
- exposing delivery state through existing WebUI/API summary views

It does not change summary generation success semantics: summary result
persistence and cursor advancement must remain successful even if notification
is skipped, times out, or fails.

## Data Model Use

Use the existing `summary_delivery_attempts` table:

- `summary_result_id`: persisted result being delivered
- `relay_bot_id`: private relay bot config id when known
- `target_chat_id`: owner chat id when known
- `status`: `pending`, `running`, `succeeded`, `failed`, `skipped`, or
  `timeout`
- `attempt_count`: total attempts made
- `max_attempts`: default `3`
- `timeout_seconds`: default `60`
- `total_chunks`, `sent_chunks`
- `telegram_message_ids`
- `error_type`, `error_message`

No migration is expected.

## Delivery Boundary

Add a service module with a small injectable boundary:

- `SummaryNotificationDispatcher`: bounded in-process async scheduler.
- `deliver_summary_notification`: DB-aware delivery operation for one result.
- `split_telegram_text`: deterministic chunking helper.

The dispatcher owns an `asyncio.Semaphore` and schedules at most a fixed number
of concurrent delivery tasks. It must not create unbounded work. If the bound is
full, it still schedules one coroutine that waits on the semaphore rather than
spawning retry storms.

The delivery operation receives:

- `session_factory`
- `bot`-like object with `send_message(chat_id, text)`
- `owner_id`
- optional `relay_bot_id`
- `summary_result_id`

Tests use fake senders only; no real Telegram calls.

## Summary Job Integration

`services/summary_jobs.py` should keep result persistence and cursor advancement
as the success path. After the job is successful, it may call an optional
notification scheduler with the created `SummaryResult.id`.

If no dispatcher is available, summary jobs stay successful and no delivery row
is required. If a dispatcher is available but no bot/owner is configured, the
dispatcher records `skipped` or `failed` without mutating the summary job.

## Web/API Contract

Extend summary result views with delivery state:

- job detail `result.delivery`
- historical summaries `delivery`

Delivery state should be safe metadata only:

- `status`
- `attempt_count`
- `max_attempts`
- `total_chunks`
- `sent_chunks`
- `target_chat_id_redacted` or nullable target indicator, not raw owner id if
  avoidable
- `error_type`
- `error_message`
- `updated_at`

Do not expose bot token, owner raw id, summary source messages, or raw Telegram
responses.

## Error Semantics

- Success: all chunks sent in one attempt; status `succeeded`.
- Retryable send errors/timeouts: retry until max attempts, then status
  `timeout` for timeouts or `failed` for send failures.
- Non-retryable send errors: status `failed`.
- Relay unavailable: status `skipped` with `error_type="relay_unavailable"`.
- Summary job/result remains unchanged for all delivery failures.

## Rollback

Rollback is service/API level. Reverting the dispatcher integration leaves
summary result persistence intact. Existing delivery attempt rows are harmless
historical metadata.
