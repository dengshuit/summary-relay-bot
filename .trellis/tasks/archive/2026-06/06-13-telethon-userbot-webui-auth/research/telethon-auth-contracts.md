# Telethon auth contracts

Verified design inputs for the first WebUI-managed userbot auth child.

## Official references

- Telethon stable docs: https://docs.telethon.dev/en/stable/
- Signing in: https://docs.telethon.dev/en/stable/basic/signing-in.html
- Sessions: https://docs.telethon.dev/en/stable/concepts/sessions.html
- Updates: https://docs.telethon.dev/en/stable/basic/updates.html
- Events: https://docs.telethon.dev/en/stable/modules/events.html

## Contracts used by this task

- Telethon clients require `api_id` and `api_hash` from `my.telegram.org`; `api_hash` is a secret.
- WebUI login maps to Telethon's phone-code flow: send a code request, then sign in with phone, code, and phone code hash.
- 2FA-enabled accounts require a password step after the code step. The backend must treat that password as a write-only secret and must not persist it.
- `StringSession` can persist a session as a string and later recreate an authorized client. The string contains account authorization material, so leaking it is account compromise.
- Proxy support belongs at Telethon client construction time. SOCKS proxy support requires the async `python-socks` extra.
- The auth implementation must be injectable/fakeable. Unit and API tests must not contact Telegram or require a real Telegram account, code, password, API hash, or session string.

## Scope boundary for this child

- This child owns userbot configuration, phone code request, code submission, optional 2FA password submission, encrypted session persistence, and safe WebUI/API status.
- Group discovery, event handlers, message ingestion, and long-running Telethon collection runtime belong to the next child.
