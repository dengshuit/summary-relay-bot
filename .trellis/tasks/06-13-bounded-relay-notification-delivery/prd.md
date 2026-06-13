# Bounded relay notification delivery

## Goal

Deliver persisted group summary results to the owner through the private relay bot as a non-blocking, bounded notification channel.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- Summary notification must run asynchronously after summary result persistence.
- Summary generation, result persistence, and cursor advancement must not depend on private relay bot availability or notification success.
- Send the full summary text to the owner through the configured private relay bot.
- Split overlong summaries into bounded Telegram message chunks while preserving complete content.
- Interpret "max two retries" as initial attempt plus at most two retries, for at most three total attempts.
- Each delivery attempt/task must have a one-minute timeout.
- Delivery execution must use bounded async work; no unbounded thread, task, or queue growth.
- Record delivery attempts with status, retry count, timeout/failure, target owner/chat, and message/chunk metadata where practical.

## Acceptance Criteria

- [ ] Persisted summary results enqueue or schedule notification without blocking the summary job result/cursor path.
- [ ] Relay bot unavailable state records skipped/failed delivery without failing the summary result.
- [ ] Full summary content is delivered when within Telegram chunk limits.
- [ ] Overlong summary content is split into ordered chunks and sent completely.
- [ ] Delivery uses at most three total attempts with one-minute timeout per attempt/task.
- [ ] Delivery worker/task concurrency is bounded and covered by tests.
- [ ] Delivery attempts and final status are visible to WebUI/API.
- [ ] Tests cover success, relay unavailable, timeout, retry exhaustion, chunking, and bounded concurrency behavior.

## Notes

- Depends on private relay runtime and summary result persistence.
