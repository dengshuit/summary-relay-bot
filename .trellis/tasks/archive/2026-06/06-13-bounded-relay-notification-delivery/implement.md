# Bounded relay notification delivery - Implementation Plan

## Ordered Steps

1. Delivery service
   - Add chunking helper with deterministic Telegram-safe limits.
   - Add DB helpers for creating/updating `SummaryDeliveryAttempt` rows if
     repository helpers are not already present.
   - Add `deliver_summary_notification` with max three attempts and
     `asyncio.timeout(60)` per attempt.
   - Add `SummaryNotificationDispatcher` with bounded concurrency.

2. Summary job integration
   - Add optional notification scheduler parameter to summary execution.
   - Schedule notification only after summary result persistence and successful
     cursor advancement.
   - Keep job success independent of delivery outcome.
   - Wire runtime scheduler/manual paths to a dispatcher when private relay
     resources are available.

3. Web/API visibility
   - Add safe delivery schema.
   - Include latest delivery attempt metadata in summary job result and
     historical summaries.
   - Keep raw owner id and secrets out of responses.

4. Tests
   - Unit-test chunking, success, long-message chunk delivery, relay unavailable,
     timeout/retry exhaustion, retry success, and concurrency bound.
   - Update summary job tests to prove notification scheduling happens after
     result/cursor success and failure does not roll back summary jobs.
   - Update API tests for delivery metadata visibility and redaction.

5. Validation
   - Run focused backend tests plus WebUI typecheck/build.

## Validation Commands

Run from the repo root:

```bash
.venv/bin/python -m compileall -q src tests migrations
.venv/bin/python -m pytest tests/unit/test_summary_notifications.py -q
.venv/bin/python -m pytest tests/unit/test_summary_jobs.py -q
.venv/bin/python -m pytest tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q
.venv/bin/python -m pytest tests/unit/test_web_groups_api.py tests/unit/test_runtime_config.py -q
cd web && npm run lint
cd web && npm run build
```

## Review Checklist

- Summary result/cursor success does not depend on notification delivery.
- Delivery attempts are bounded by concurrency, max attempts, and timeout.
- Overlong summaries are delivered completely in ordered chunks.
- Delivery failures are recorded and do not mutate successful summary jobs.
- API responses expose only safe delivery metadata.
- Tests use fake senders only; no real Telegram calls.
