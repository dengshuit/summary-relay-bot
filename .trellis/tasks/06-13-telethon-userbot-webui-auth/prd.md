# Telethon userbot WebUI authorization

## Goal

Add WebUI-managed Telethon userbot configuration and authorization with secure credential/session handling.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- Support one enabled Telethon userbot account in the first implementation.
- Configure `api_id`, encrypted `api_hash`, phone number, optional proxy settings, and encrypted Telethon session through WebUI.
- Support full authorization flow: send phone code, submit code, handle optional 2FA password, and persist the resulting session.
- Store Telethon session data securely; do not expose session strings in API responses, logs, audit logs, or UI.
- Show authorization/runtime state in WebUI: unconfigured, code sent, 2FA required, authorized, running, failed, disabled.
- Use official Telethon stable docs as design input for `TelegramClient`, `StringSession`, events, sessions, and proxy support.
- Do not require private relay bot runtime to be running to configure or authorize userbot.

## Acceptance Criteria

- [ ] WebUI/API can create/update a single enabled userbot configuration.
- [ ] Code request, code submission, and 2FA password submission flows are implemented.
- [ ] Successful authorization stores an encrypted session and displays only safe status metadata.
- [ ] Userbot `api_hash`, phone code, 2FA password, and session string are never returned or logged.
- [ ] Runtime status and last error are visible through WebUI/API.
- [ ] Tests cover successful auth, 2FA-required flow, validation errors, redaction, and one-enabled-userbot enforcement.

## Notes

- Depends on schema reset for userbot configuration tables.
