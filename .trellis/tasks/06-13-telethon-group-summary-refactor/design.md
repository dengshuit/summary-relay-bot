# Refactor bot architecture for Telethon group summaries - Design

## Architecture

The refactor keeps one deployable Python/WebUI process and one database, but splits runtime and domain ownership:

- Private relay runtime: aiogram/Bot API runtime for private relay, owner replies, private-relay-specific commands, and summary notification delivery.
- Summary userbot runtime: Telethon/MTProto runtime for userbot authorization, group discovery, enabled-group message collection, and collection status.
- WebUI/API: the only control plane for group summary configuration, userbot authorization, group enablement, manual summary trigger, and summary result inspection.
- Scheduler/workers: in-process scheduled summary jobs and bounded async notification delivery.

The two runtime managers must expose independent configuration, status, reload, stop, and error state. A userbot failure must not prevent private relay from running. A relay bot failure must not prevent summary generation, result persistence, or summary cursor advancement.

## Data Model Boundaries

Use domain-oriented tables rather than stretching the current single-bot schema.

Relay domain:

- relay bot configuration and status
- private relay users/messages
- private relay reply maps

Summary domain:

- summary userbot configuration and authorization/session status
- discovered summary entities/groups with `userbot_id`, Telegram entity identifiers, entity type, title/username, enabled state, summary settings, and future channel/backfill room
- normalized summary messages with Telegram message id/date/edit/delete metadata, sender display metadata, message type, text/caption/summary content, and media placeholder metadata
- summary state/cursor, summary jobs, and summary results
- summary notification delivery attempts

LLM domain:

- reuse existing LLM Provider and Summary Profile configuration and default profile behavior
- summary group settings reference Summary Profiles

Fresh database initialization is required. Existing development data does not need to be migrated or preserved.

## Telethon Contracts

Use official Telethon stable docs as the source for API behavior.

- Use an asyncio `TelegramClient`.
- Store `api_hash` and session data as secrets.
- Support WebUI-driven login: send code, submit code, handle 2FA password, persist encrypted session.
- Use `StringSession` or an equivalent encrypted persisted session representation.
- Treat session leakage as account compromise in docs and UI safety text.
- Use `events.NewMessage` for new messages, `MessageEdited` for edits, and `MessageDeleted` for delete metadata when practical.
- For update events, fetch chat/sender through Telethon methods when full data is needed.
- Do not persist complete raw Telethon event payloads.
- Do not actively backfill with `iter_messages` / `get_messages` in the first implementation.
- Allow reconnect-delivered update-stream messages to be stored and summarized.

## Summary Flow

1. User authorizes one enabled Telethon userbot in WebUI.
2. Summary userbot runtime starts, scans visible groups once, and writes discovered entities as disabled by default.
3. User explicitly enables groups in WebUI and configures summary settings/profile.
4. Telethon events for enabled groups are normalized and stored.
5. WebUI manual trigger or scheduler creates a summary job.
6. Summary job reads messages after the group cursor, calls the existing LLM summary client, persists `summary_results`, and advances the cursor.
7. A bounded asynchronous notification task attempts to send the full summary through the private relay bot.
8. WebUI remains the authoritative source for summary content and delivery status.

Telegram notification failure must not roll back result persistence or cursor advancement.

## Notification Contract

Summary notification through the private relay bot is a best-effort delivery channel:

- full summary text is sent when possible
- overlong summaries are split into ordered chunks
- initial attempt plus at most two retries
- one-minute timeout per attempt/task
- bounded worker/task concurrency
- no unbounded threads, queues, or background task creation
- delivery attempts record status and errors for WebUI inspection

## Command Boundary

Group summary management is WebUI-only:

- remove `/groups`, `/summary`, `/enable_group`, `/disable_group`, and `/set_interval` from Telegram bot command menus and handlers
- non-owner users see/use only `/start` and `/help`
- owner/admin keeps private-relay-related commands such as `/reply`
- ordinary private relay and mapped replies remain supported

## Rollout Shape

This is a development-stage schema reset:

- no production data migration guarantee
- documentation must tell users to recreate/reset the database for this refactor
- child tasks should land in an order that keeps tests meaningful at each step
- the parent task is complete only after all children pass their own validation and the final integration child verifies the full workflow
