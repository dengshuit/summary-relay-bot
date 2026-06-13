# Telethon group discovery and ingestion

## Goal

Use the authorized Telethon userbot to discover visible groups and collect enabled-group messages into normalized summary-domain storage.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- Scan userbot-visible dialogs/groups once when the userbot runtime starts.
- Provide a WebUI-triggerable refresh action for group discovery.
- Newly discovered groups default to disabled.
- Only enabled groups are collected and summarized.
- First implementation supports groups, supergroups, and Telethon megagroups; broadcast channels are out of scope but entity type metadata must be stored.
- First implementation must not actively fetch historical messages with `iter_messages` or `get_messages`.
- Telethon update-stream messages delivered after reconnect may be stored and summarized.
- Normalize message content and required metadata without storing full raw Telethon event payloads.
- Store text/caption, summary content, message type, sender display metadata, Telegram message id/date, edit/delete metadata, entity type, and media placeholder metadata.
- Handle edits for not-yet-summarized messages by updating normalized content and `edited_at`.
- Mark deletions when practical, but do not retract or regenerate historical summaries.

## Acceptance Criteria

- [ ] Userbot startup scans visible groups and stores disabled group records.
- [ ] WebUI/API can refresh group discovery without restarting the application.
- [ ] Disabled groups do not store incoming messages.
- [ ] Enabled groups store new Telethon `NewMessage` updates with stable deduplication.
- [ ] Reconnect-delivered update-stream messages are treated as normal new messages.
- [ ] Broadcast channels are ignored for first-version collection.
- [ ] Message normalization handles text and common media placeholders.
- [ ] Message edits update not-yet-summarized content and preserve edit metadata.
- [ ] Message delete events can mark messages deleted without rewriting summary results.
- [ ] Tests cover discovery, explicit enablement, deduplication, disabled-group ignore behavior, normalization, edits, and delete marking.

## Notes

- Depends on schema reset and userbot authorization/runtime.
