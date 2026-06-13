# Refactor bot architecture for Telethon group summaries

## Goal

Refactor the project from a single Bot API-centered backend into two independent product domains sharing one WebUI and one database:

- Private relay bot: keeps the current Bot API / aiogram-based private message relay workflow.
- Group summary service: uses a Telethon userbot for group message collection, stores summaries for WebUI review, and uses the private relay bot as the Telegram notification channel to the owner.

The project is still in development and not yet used in production, so the implementation may favor a clean maintainable backend redesign over compatibility-preserving bridge code.

## Confirmed Facts

- Current group collection is implemented through aiogram Bot API polling in `src/summary_relay_bot/handlers/group.py`.
- Current group message extraction and storage are centered on aiogram `Message` objects and `TelegramUpdate.update_id`.
- Current summary jobs read local `GroupMessage.id > SummaryState.last_summary_sequence`.
- Current summary delivery advances the cursor only after LLM generation and Telegram private delivery both succeed.
- The user wants WebUI visibility for group summaries even when Telegram notification is also sent.
- The user wants group summary Telegram notifications to be sent through the current private relay bot rather than a separate delivery bot.
- The user does not want a separate database, but table/domain separation is acceptable.
- The user wants userbot configuration and login to be manageable from WebUI.
- First Telethon implementation should collect only new messages after userbot startup; schema/design should reserve room for future historical backfill.
- First WebUI userbot configuration should support the full Telethon login flow, including sending a phone code, submitting the code, handling 2FA password when required, and storing the resulting encrypted session.
- Existing development data does not need to be preserved. The new schema only needs correct initialization for fresh databases.
- Telethon should be allowed to discover visible groups, but message collection and summary generation should only run for groups explicitly enabled in WebUI.
- Group summary generation must not depend on the private relay bot being configured or available.
- Summary Telegram notification through the private relay bot should run asynchronously after summary persistence.
- Summary notification delivery must be bounded: at most two retries, one-minute timeout per delivery task, and no unbounded thread/task creation.
- First group summary implementation supports group/supergroup/Telethon megagroup conversations only, not broadcast channels.
- Schema/design should reserve entity type fields needed for later broadcast channel support.
- Userbot-collected messages should store normalized summary content and necessary metadata only, not full raw Telethon event payloads.
- Group summary management should be WebUI-only in the first implementation.
- The private relay bot should keep private relay command/functionality boundaries: third-party users should only see `/start` and `/help`, while the owner/admin command surface should remove only group-summary-related commands.
- Existing private relay behavior remains in scope, including ordinary third-party private message forwarding, owner replies through reply mapping, and private-relay-related owner commands such as `/reply`.
- WebUI should retain manual immediate summary triggering in addition to scheduled summaries.
- Summary notification through the private relay bot should send the full summary text. If the summary is too long for Telegram message limits, split it into bounded message chunks.
- The first implementation supports one enabled Telethon userbot account.
- Schema should retain `userbot_id` ownership fields where useful so multiple userbot accounts can be added later without redesigning summary storage.
- Reuse the existing LLM Provider and Summary Profile configuration model for group summaries.
- First implementation should handle message edits but not full delete rollback.
- First implementation stays in one Python/WebUI process, with separate runtime managers and lifecycle state for private relay and summary userbot collection.
- Userbot-visible group discovery should scan once on userbot runtime startup and be manually refreshable from WebUI.
- Telethon updates automatically delivered after reconnect may be stored and summarized; the first implementation still must not actively fetch historical messages.
- Implementation should be split into independently verifiable child tasks under this parent task.

## External Research Facts

Verified against official Telethon stable docs and PyPI on 2026-06-13:

- Telethon is an asyncio Python MTProto client for user accounts or bot accounts.
- Telethon requires an application `api_id` and `api_hash` from `my.telegram.org`; the API hash is secret.
- Telethon supports proxy configuration through `proxy=...`; SOCKS proxy support requires `python-socks[asyncio]`.
- Telethon session storage contains the authorization key and entity cache needed to use the account without re-login.
- Telethon provides `StringSession`, which can be stored as a string and reused, but leaking it lets another party use the Telegram account.
- `events.NewMessage` handles new text or media messages and supports chat filtering through the `chats` argument.
- Telethon event handlers must be `async def`; network calls must be awaited.
- For update events, Telethon docs recommend `await event.get_chat()` and `await event.get_sender()` instead of relying on partial event properties.
- Latest PyPI Telethon version observed: `1.43.2`.

Primary references:

- https://docs.telethon.dev/en/stable/
- https://docs.telethon.dev/en/stable/basic/signing-in.html
- https://docs.telethon.dev/en/stable/concepts/sessions.html
- https://docs.telethon.dev/en/stable/basic/updates.html
- https://docs.telethon.dev/en/stable/modules/events.html

## Requirements

- Keep one WebUI and one application database.
- Keep one deployable Python process for the first implementation.
- Split private relay and group summary into separately understandable backend domains.
- Run private relay and group summary collection through independent runtime managers with independent configuration, status, start/stop/reload, and error reporting.
- Keep private relay on Bot API / aiogram.
- Non-owner Telegram users should only see and use `/start` and `/help` on the private relay bot.
- Owner/admin Telegram command surface should retain private-relay-related commands and remove group-summary-related commands.
- Preserve ordinary private relay message forwarding, reply-map owner replies, and private-relay-specific owner commands.
- Remove or do not register Telegram commands for group summary management, including `/groups`, `/summary`, `/enable_group`, `/disable_group`, and `/set_interval`.
- Provide WebUI controls for manual immediate summary generation.
- Provide WebUI controls for per-group scheduled summary configuration.
- Group summary settings should reference existing Summary Profiles and default Summary Profile behavior.
- Use Telethon userbot for group summary message collection.
- In the first implementation, collect only messages received after the userbot runtime starts.
- Treat Telethon update-stream messages delivered after reconnect as normal new messages when the target group is enabled.
- Do not actively call historical message APIs such as `iter_messages` / `get_messages` for backfill in the first implementation.
- Discover userbot-visible groups for WebUI management without storing all messages by default.
- Scan userbot-visible dialogs/groups when the summary userbot runtime starts.
- Provide a WebUI action to manually refresh the userbot-visible group list.
- Only collect and summarize messages for groups explicitly enabled in WebUI.
- Newly discovered groups must default to disabled.
- Treat broadcast channels as out of scope for first-version collection and summarization.
- Store enough Telegram entity type metadata to add broadcast channel support later without another domain rewrite.
- Store normalized message fields needed for summarization, WebUI inspection, deduplication, and future backfill: summary content, text/caption when applicable, message type, sender display metadata, Telegram message id, message date, edit date, entity type, and media placeholder metadata.
- Do not persist complete Telethon raw event dictionaries or full MTProto payloads in the first implementation.
- If an already-collected but not-yet-summarized message is edited, update its normalized content and `edited_at`.
- If an already-summarized message is edited, record that it was edited after summarization but do not rewrite historical summary results.
- If a collected message is deleted, mark it deleted when practical, but do not retract or regenerate already-created summaries in the first implementation.
- Design message storage so future historical backfill can be added without redefining the entire summary cursor model.
- Store group summaries and delivery state so WebUI can show them independently of Telegram notification success.
- Deliver group summary notifications to the owner through the configured private relay bot.
- Treat private relay bot notification as a non-blocking delivery channel: summary result persistence and summary cursor advancement must not depend on notification success.
- Implement summary notification delivery with bounded async execution, at most two retries, and a one-minute timeout per attempt/task.
- Send full summary content through the private relay bot notification channel when available, splitting overlong content into multiple Telegram messages rather than replacing it with a short notification.
- Do not create unbounded threads, goroutines, queues, or background tasks for summary notification delivery.
- Provide WebUI-managed userbot configuration and authorization flow.
- WebUI userbot authorization must support phone code login and 2FA password submission in the initial implementation.
- Enforce at most one enabled userbot in the first implementation.
- Encrypt or otherwise protect all userbot secrets, including `api_hash` and persisted session data.
- Avoid logging or returning userbot secrets, phone verification codes, 2FA passwords, session strings, bot tokens, or LLM keys.
- Prefer clean domain tables over stretching existing generic tables when the old schema makes the new model harder to maintain.
- Do not write compatibility migration logic for preserving existing development data.
- Database setup must initialize the new schema cleanly for an empty database.
- Preserve the ability to run and configure private relay without depending on a working userbot session.
- Preserve the ability to inspect group summaries in WebUI even if Telegram notification fails.

## Acceptance Criteria

- [ ] Private relay and group summary runtime responsibilities are separated in code and configuration.
- [ ] One application process can host WebUI, private relay runtime, summary userbot runtime, scheduler, and bounded delivery workers.
- [ ] Private relay runtime and summary userbot runtime expose independent WebUI-visible status and errors.
- [ ] WebUI exposes private relay bot configuration and userbot summary collector configuration as distinct concepts.
- [ ] Userbot configuration flow supports storing Telethon credentials/session without exposing secrets in API responses or logs.
- [ ] Userbot WebUI flow supports code request, code submission, optional 2FA password submission, authorization status display, and encrypted session persistence.
- [ ] Runtime starts at most one enabled Telethon userbot collector.
- [ ] Summary group/message tables retain userbot ownership metadata needed for future multi-userbot support.
- [ ] Telethon group collection can store new group messages into summary-domain tables with stable deduplication.
- [ ] Telethon group collection does not backfill historical messages in the first implementation.
- [ ] Telethon reconnect-delivered updates can be stored and summarized without adding active historical backfill.
- [ ] Telethon group collection ignores message storage for groups that are not explicitly enabled.
- [ ] Newly discovered userbot-visible groups appear in WebUI as disabled until explicitly enabled.
- [ ] WebUI can manually refresh the userbot-visible group list without restarting the application process.
- [ ] Broadcast channels are not collected or summarized in the first implementation.
- [ ] Summary group/entity schema records source entity type information needed for future channel support.
- [ ] Message schema includes enough source/time/Telegram identifiers to support a later historical backfill design.
- [ ] Userbot ingestion persists normalized message content and required metadata without storing full raw Telethon event payloads.
- [ ] Message edits update not-yet-summarized message content and preserve audit metadata.
- [ ] Edits/deletions after summarization do not rewrite historical summary results in the first implementation.
- [ ] Summary jobs generate and persist results visible in WebUI.
- [ ] Summary result persistence and cursor advancement do not depend on Telegram notification delivery succeeding.
- [ ] Telegram notification attempts through the private relay bot are recorded with success/failure status.
- [ ] Telegram notification attempts are dispatched asynchronously and bounded by max retry and timeout settings.
- [ ] Telegram notification timeout or relay bot unavailability leaves the summary result visible in WebUI and does not roll back the summary cursor.
- [ ] Overlong summary notifications are split into bounded Telegram message chunks while preserving the complete summary content.
- [ ] Tests prove delivery retry/timeout behavior does not create unbounded concurrent work.
- [ ] Existing private relay workflows remain testable and do not require Telethon to be configured.
- [ ] Ordinary private message relay, mapped owner replies, and private-relay-specific owner commands continue to work after group summary commands move to WebUI.
- [ ] Non-owner private relay bot command menu and handlers expose only `/start` and `/help`.
- [ ] Owner/admin private relay bot command menu and handlers do not expose group-summary-related commands.
- [ ] Group summary configuration, enabling/disabling, manual trigger, and result inspection are available through WebUI, not Telegram bot commands.
- [ ] WebUI manual summary and scheduled summary share the same summary job pipeline with distinct trigger types.
- [ ] Group summary jobs use the existing LLM Provider and Summary Profile runtime configuration path.
- [ ] Existing LLM Provider and Summary Profile WebUI/API behavior remains available.
- [ ] Schema reset behavior is documented; no legacy development data migration is required.
- [ ] Fresh database initialization creates the new relay and summary tables correctly.
- [ ] Documentation clearly states that existing development data is not preserved by this refactor.
- [ ] Relevant unit/integration tests cover userbot config validation, message normalization, summary result persistence, and delivery failure behavior.

## Task Map

- `06-13-telethon-schema-domain-reset`: fresh schema initialization and domain table boundaries.
- `06-13-private-relay-domain-cleanup`: private relay command/menu cleanup and relay-domain preservation.
- `06-13-telethon-userbot-webui-auth`: WebUI-managed Telethon credentials, phone code, 2FA, session persistence, and runtime status.
- `06-13-telethon-group-discovery-ingestion`: userbot group discovery, explicit enablement, new message ingestion, edit/delete metadata, and no active history backfill.
- `06-13-summary-job-persistence-refactor`: WebUI manual/scheduled summary jobs, result persistence, cursor advancement, and LLM profile reuse.
- `06-13-bounded-relay-notification-delivery`: asynchronous private relay bot notifications with full summary, chunking, bounded retries, timeout, and delivery records.
- `06-13-webui-integration-docs-validation`: integrated WebUI experience, documentation, and final cross-child validation.

The parent task owns cross-child requirements and final integration review. Child tasks own implementation artifacts and validation for their specific deliverables.

## Out of Scope

- Separate physical databases.
- Public in-group summary posting.
- Multi-owner/RBAC unless needed by the existing WebUI authentication model.
- Downloading and storing full media file bodies.
- Userbot sending arbitrary replies or interacting with private users.
- Production data migration guarantees beyond the decision made during planning.

## Open Questions

- None blocking PRD scope. Technical details should be resolved in `design.md` and child task planning before implementation starts.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
