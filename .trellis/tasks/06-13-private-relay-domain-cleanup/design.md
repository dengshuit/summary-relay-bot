# Private relay domain cleanup - Design

## Scope

This child keeps the aiogram/Bot API runtime as the private relay domain and removes Telegram-command ownership of group summary management. It does not implement Telethon userbot auth, group discovery, summary job persistence changes, or bounded summary notification delivery beyond preserving relay-domain hooks needed by later children.

The previous schema child introduced relay-domain tables and temporary compatibility aliases. This child should move private-relay code and focused tests toward the relay names where practical, but should not perform a broad cross-app rename if that would overlap later summary children.

## Command Boundary

Telegram command ownership after this child:

- Owner private chat: `/start`, `/help`, `/reply`.
- Non-owner private chat: `/start`, `/help`.
- Group chats: no group summary command menu/handlers.
- Removed from command menus and handler registration: `/groups`, `/summary`, `/enable_group`, `/disable_group`, `/set_interval`.

Command menu scopes are only visibility hints. Server-side filters must still enforce owner/private/non-owner behavior.

Owner `/help` must match the new command boundary and must not advertise removed group-summary commands.

Non-owner private messages that start with removed/unknown slash commands should be handled as unsupported commands, not forwarded to the owner as ordinary relay content. Non-owner plain text and media messages continue through private relay.

## Handler Boundary

Keep:

- private non-owner `/start` and `/help` guidance handled before the private-user catch-all
- private non-owner ordinary messages forwarded to the owner
- owner replies routed through reply maps
- owner `/reply <user_id> <message>`
- owner `/start` and `/help`

Remove or stop registering:

- `admin_groups` summary management handlers
- owner `/summary` handler from `admin.py`
- group message collection handler from the private relay dispatcher, if it is only for Bot API group summary collection

If group collection modules remain in the codebase temporarily for later removal, they must not be wired into the relay runtime.

## Runtime Independence

Private relay runtime must continue to load from relay bot configuration only. It must not depend on `summary_userbots`, Telethon session state, summary entity configuration, or group summary runtime availability.

The runtime build path should still include:

- Bot creation from encrypted relay token
- owner filter configuration
- private relay handler registration
- command menu setup
- scheduler only for private-relay-owned jobs if any remain

If scheduler currently owns summary jobs, this child may leave the scheduler object mounted but must remove Telegram command paths that trigger group summary management. Full scheduler refactor belongs to summary job persistence.

## Data/Name Compatibility

Prefer relay-domain names for touched code:

- `RelayBot` over `BotInstance`
- `RelayPrivateUser` over `PrivateUser`
- `RelayPrivateMessage` over `PrivateMessage`
- `RelayReplyMap` over `AdminReplyMap`
- `RelayDeliveryAttempt` over generic `DeliveryAttempt`

Temporary compatibility aliases from the schema child may remain if broad WebUI/API migration would exceed this child. Any touched tests should assert behavior, not old table names.

This child must not remove the schema-reset compatibility aliases in `db.models`; later children will remove them while moving summary services and WebUI/API code to new domain names.

## Security

Do not log or return bot tokens, encrypted token material, admin tokens, or raw private message content beyond existing tested preview/redaction behavior.

## Tests

Required regression coverage:

- owner command menu excludes group summary commands and includes `/reply`
- non-owner command menu exposes only `/start` and `/help`
- router registration or handler tests prove group summary handlers are not included in the relay dispatcher
- `admin.build_router()` no longer registers `/summary`
- owner help text excludes removed commands
- non-owner removed/unknown slash commands are not relayed as private messages
- non-owner ordinary private messages still persist and forward
- mapped owner replies and `/reply` still work
- private relay runtime can start/build without any `summary_userbots` row
