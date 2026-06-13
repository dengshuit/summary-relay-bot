# Refactor bot architecture for Telethon group summaries - Implementation Plan

## Execution Order

1. `06-13-telethon-schema-domain-reset`
   - Design and initialize the fresh schema for relay and summary domains.
   - Keep LLM Provider and Summary Profile behavior reusable.
   - Validate empty-database initialization.

2. `06-13-private-relay-domain-cleanup`
   - Move relay behavior into the relay domain boundaries.
   - Preserve private message forwarding, reply maps, `/reply`, `/start`, and `/help`.
   - Remove group summary commands from bot menus and handlers.

3. `06-13-telethon-userbot-webui-auth`
   - Add Telethon dependency and userbot config APIs.
   - Implement WebUI authorization flow: code request, code submission, 2FA, encrypted session persistence.
   - Add independent userbot runtime status.

4. `06-13-telethon-group-discovery-ingestion`
   - Implement startup group scan and WebUI manual refresh.
   - Add explicit enablement.
   - Ingest enabled-group `NewMessage` updates and normalize content.
   - Handle edit/delete metadata without historical summary rewrite.

5. `06-13-summary-job-persistence-refactor`
   - Rework WebUI manual and scheduled summaries around persisted summary results.
   - Advance cursor after result persistence, independent of Telegram delivery.
   - Reuse existing LLM Provider and Summary Profile runtime config.

6. `06-13-bounded-relay-notification-delivery`
   - Add bounded async delivery after result persistence.
   - Implement full-summary chunking, initial attempt plus two retries, one-minute timeout, and delivery attempt records.

7. `06-13-webui-integration-docs-validation`
   - Complete WebUI integration across relay and summary domains.
   - Update README/operations docs.
   - Run cross-child validation and regression tests.

## Review Gates

- Each child task must have its own `design.md` and `implement.md` before `task.py start`.
- Each child task must define targeted validation commands before implementation starts.
- Do not start a later child if an earlier child leaves schema or runtime contracts unresolved.
- Parent integration review must confirm:
  - private relay works without userbot configuration
  - group summary works without relay notification success
  - WebUI can configure userbot, enable groups, trigger summaries, and inspect results/delivery attempts
  - no raw Telethon session/code/2FA secrets are returned or logged

## Expected Validation

- Backend unit tests for repositories, runtime config, command routing, Telethon auth service, ingestion normalization, summary jobs, delivery retries/timeouts.
- Backend integration tests for empty database initialization and cross-domain workflows.
- Frontend type/build checks and focused WebUI tests where available.
- Documentation review for setup, schema reset, Telethon session risk, and first-version limitations.

## Rollback Points

- Schema reset child should be reviewed before runtime children begin.
- Private relay cleanup should preserve old private relay behavior before Telethon work begins.
- Userbot auth should be validated with fakes/mocks before live Telegram testing is required.
- Summary result persistence should be verified before enabling asynchronous notification delivery.
