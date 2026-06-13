# Private relay domain cleanup

## Goal

Keep the Bot API / aiogram private relay bot focused on private relay and notification delivery while removing group summary command ownership from Telegram bot commands.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- Preserve ordinary third-party private message forwarding to the owner.
- Preserve owner replies through reply maps.
- Preserve private-relay-specific owner commands, including `/reply`.
- Non-owner users should only see/use `/start` and `/help`.
- Owner/admin command menu and handlers must remove group-summary-related commands: `/groups`, `/summary`, `/enable_group`, `/disable_group`, and `/set_interval`.
- Private relay runtime must be independently configurable and must not require Telethon userbot configuration to run.
- The private relay bot can later be used by summary notification delivery, but summary management remains WebUI-only.

## Acceptance Criteria

- [ ] Non-owner private command menu exposes only `/start` and `/help`.
- [ ] Owner/admin command menu excludes group summary commands.
- [ ] `/reply` and mapped owner replies continue to work for private relay.
- [ ] Ordinary non-owner private messages are still persisted and forwarded to the owner.
- [ ] Private relay runtime can start without a configured/authorized userbot.
- [ ] Tests cover command routing for owner and non-owner users after group summary commands are removed.

## Notes

- This child can follow schema reset if relay table names or repositories change.
