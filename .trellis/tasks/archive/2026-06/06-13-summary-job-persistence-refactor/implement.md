# Summary job persistence refactor - Implementation Plan

## Ordered Steps

1. Shared persistence core
   - Extract or consolidate the duplicated summary execution logic in
     `services/summary_jobs.py`.
   - Ensure manual and scheduled jobs both create/persist `SummaryResult` before
     cursor advancement.
   - Remove Telegram send success from the success path for this child.

2. WebUI manual job path
   - Keep pending-job trigger and poll URL behavior.
   - Make `run_web_manual_summary_job` use the shared core.
   - Preserve conflict behavior for active jobs.

3. Scheduled path
   - Keep scheduler entrypoint and enabled-group checks.
   - Make scheduled jobs use the same core and `trigger_type="scheduled"`.

4. Compatibility path
   - Keep `run_summary_for_group` callable for existing bot/runtime tests.
   - Return updated `SummaryRunResult` messages that reflect persistence and
     cursor advancement rather than Telegram delivery.

5. Tests
   - Update summary job unit tests to assert delivery failure no longer blocks
     result persistence or cursor advancement.
   - Add/adjust tests for no-message jobs, successful result persistence,
     cursor advancement, runtime config failure cursor safety, LLM failure
     cursor safety, and WebUI poll/result visibility.
   - Keep API redaction assertions.

6. Task status
   - Mark this child complete only after targeted backend and WebUI validation
     passes.

## Validation Commands

Run from the repo root:

```bash
.venv/bin/python -m compileall -q src tests migrations
.venv/bin/python -m pytest tests/unit/test_summary_jobs.py -q
.venv/bin/python -m pytest tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_summaries_api.py -q
.venv/bin/python -m pytest tests/unit/test_web_groups_api.py tests/unit/test_runtime_config.py -q
.venv/bin/python -m pytest tests/integration/test_persistence.py -q
cd web && npm run lint
cd web && npm run build
```

## Review Checklist

- Manual and scheduled production jobs share the same persistence semantics.
- Successful LLM generation creates exactly one `SummaryResult`.
- Cursor advances only after result persistence succeeds.
- Runtime config and LLM failures leave cursor unchanged.
- Telegram/private relay notification is not required for job success in this
  child.
- API responses do not expose raw source group messages or secrets.
