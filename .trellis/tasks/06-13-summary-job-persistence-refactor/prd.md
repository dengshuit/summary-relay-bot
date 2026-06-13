# Summary job persistence refactor

## Goal

Refactor group summary jobs so WebUI manual and scheduled summaries persist results and advance cursors independently of Telegram notification delivery.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- Provide WebUI-triggered manual immediate summary jobs.
- Provide per-group scheduled summaries.
- Manual and scheduled summaries must share one job pipeline with distinct trigger types.
- Reuse existing LLM Provider and Summary Profile runtime configuration and default profile behavior.
- Read normalized summary messages for enabled groups from the new summary-domain storage.
- Generate and persist `summary_results` before private relay notification.
- Advance summary cursor after successful LLM generation and result persistence, not after Telegram notification.
- Failed LLM/runtime config should leave cursor unchanged and record job failure.
- Edits/deletions after summarization must not rewrite historical summary results in the first implementation.
- WebUI must be able to inspect summary jobs, results, errors, sequence/cursor ranges, and delivery state.

## Acceptance Criteria

- [ ] WebUI/API can trigger a manual summary job for a group.
- [ ] Scheduled summary jobs run for enabled groups at configured intervals.
- [ ] Manual and scheduled jobs share the same service and use distinct `trigger_type` values.
- [ ] Summary jobs use existing LLM Provider and Summary Profile configuration.
- [ ] Successful LLM output creates a persisted summary result visible in WebUI.
- [ ] Summary cursor advances after result persistence even when relay notification is unavailable.
- [ ] LLM/runtime config failure records a failed job and leaves the cursor unchanged.
- [ ] Tests cover no-message behavior, successful result persistence, cursor advancement, failure cursor safety, and LLM profile reuse.

## Notes

- Depends on schema reset and message ingestion storage.
- Notification delivery is handled by `06-13-bounded-relay-notification-delivery`.
