# Telethon group discovery and ingestion - Design

## Scope

This child connects the authorized summary userbot to group discovery and normalized message ingestion:

- discover visible group/supergroup/megagroup dialogs
- store newly discovered groups disabled by default
- expose a WebUI/API refresh action
- ingest only enabled-group update-stream messages
- normalize text/caption/media placeholder metadata without storing full raw Telethon payloads
- update edit metadata for existing messages
- mark deletes when possible

It does not implement summary generation changes, notification delivery, historical backfill, or a long-running production-grade runtime supervisor beyond the fakeable ingestion/discovery boundary needed by this child.

## Data Model Use

Use schema-reset tables already present:

- `summary_userbots`
- `summary_entities`
- `summary_messages`
- `summary_states`

No new migration is planned unless implementation discovers a schema contradiction.

Group records map to `SummaryEntity`:

- `userbot_id`: owning summary userbot
- `telegram_entity_id`: Telethon chat/entity id
- `telegram_access_hash`, `telegram_peer_type`, `entity_type`
- `title`, `username`
- `enabled` defaults to `False`
- `collection_status` defaults to `disabled`
- `discovered_at`, `last_seen_at`, `last_refreshed_at`

Message records map to `SummaryMessage`:

- unique `(entity_id, telegram_message_id)` provides stable deduplication
- `source_kind='telethon_update'`
- `message_date`, `edited_at`, `deleted_at`, `edited_after_summary_at`
- sender metadata
- `message_type`, `text`, `caption`, `summary_content`
- media placeholders in `media_metadata`

## Service Boundary

Add a dedicated summary userbot ingestion service rather than extending old aiogram update-ingest code.

Core data types:

- `DiscoveredDialog`: normalized dialog metadata returned by the Telethon adapter/fakes
- `IncomingMessage`: normalized message-event input
- `EditedMessage`: normalized edit-event input
- `DeletedMessage`: normalized delete-event input

Core operations:

- `refresh_userbot_dialogs(session, userbot, dialogs)`: upsert supported dialogs as disabled groups, refresh metadata, ignore broadcast channels for collection
- `ingest_userbot_message(session, message)`: store enabled-group new message, ignore disabled/unknown/unsupported entities, dedupe by `(group_id, telegram_message_id)`
- `ingest_userbot_message_edit(session, edit)`: update normalized content for not-yet-summarized messages; if already summarized, preserve old content and set `edited_after_summary_at`
- `mark_userbot_message_deleted(session, delete)`: mark `deleted_at` for known messages

The service must not call Telegram directly. Telethon-specific runtime/adapters pass normalized DTOs into the service, making tests fully fakeable.

## Telethon Adapter Boundary

Extend the userbot Telegram boundary with discovery/runtime-facing helpers only:

- parse dialog/chat objects into `DiscoveredDialog`
- parse new/edit/delete events into normalized DTOs
- keep actual `TelegramClient` construction behind the existing userbot runtime config

Tests for this child should use fake DTOs and not instantiate Telethon clients.

## API/WebUI Contract

Expose a manual refresh action under existing `/api/groups` because group management already belongs there:

- `POST /api/groups/refresh-userbot`
  - requires admin bearer token
  - loads enabled authorized userbot runtime config
  - calls an injectable dialog discovery provider
  - upserts supported dialogs
  - returns `{ discovered, created, updated, ignored }`

If no authorized enabled userbot exists, return `409 conflict` with a safe error message.

Group list/detail schemas should continue to use existing fields. Discovered groups appear disabled by default and can be enabled through the existing summary-settings endpoint.

## Normalization Rules

- Supported collection entity types: `group`, `supergroup`, `megagroup`
- Broadcast channels are discovered with metadata only when useful, but not collected in this child.
- Disabled groups do not store incoming messages.
- Unknown groups are ignored by message ingestion; discovery is responsible for creating group rows.
- Text messages use `message_type='text'`.
- Captioned media uses a media-specific `message_type` when detectable; otherwise `media`.
- `summary_content` is text/caption when present; otherwise a stable placeholder such as `[media: photo]`.
- Do not persist raw event dictionaries, raw MTProto objects, or full media bytes.

## Edit/Delete Semantics

Edit:

- If the message sequence is greater than `SummaryState.last_summary_sequence`, update `text`, `caption`, `summary_content`, `message_type`, metadata, and `edited_at`.
- If the message has already been summarized, do not rewrite content; set `edited_after_summary_at` if absent and keep `edited_at` metadata.

Delete:

- For known message ids, set `deleted_at`.
- Do not delete rows and do not rewrite summary results.

## Validation

Tests must cover:

- discovery creates disabled groups and refreshes existing metadata
- broadcast/channel dialogs are ignored for collection
- disabled-group messages are ignored
- enabled-group new messages are stored and deduped
- message normalization for text and media placeholders
- edits update unsummarized messages
- edits after summary preserve content and mark `edited_after_summary_at`
- delete marking
- refresh API auth, no-userbot conflict, success, and safe response shape
