# Telegram Summary Relay Bot Operations

## Startup checklist

1. Create the PostgreSQL database and run `alembic upgrade head`.
2. Set the bootstrap env: `DATABASE_URL`, `SETTINGS_ENCRYPTION_KEY`, `WEBUI_ADMIN_TOKEN`, `WEBUI_HOST`, and `WEBUI_PORT`.
3. Start exactly one bot service process. Empty databases and databases with no enabled bot still start the WebUI; Telegram polling does not start until an enabled bot can be loaded and decrypted.
4. Open the WebUI and log in with `WEBUI_ADMIN_TOKEN`.
5. Create a Telegram bot with BotFather, then configure its Bot token and owner ID in the WebUI.
6. Ensure no webhook is configured for this bot token before starting polling.
7. Have the administrator send `/start` to the bot privately.
8. Add the bot to groups that should be collected.
9. If ordinary group messages are not received, review BotFather privacy mode and re-add the bot after changing it.
10. Run exactly one polling process for one bot token.

## WebUI and deployment

The production deployment is a monolith. The same Python service:

- Runs Telegram polling when an enabled Bot instance is available.
- Serves authenticated management APIs under `/api/*`.
- Serves the React/Vite build copied from `web/dist`.
- Falls back to the SPA `index.html` for non-API routes such as `/groups/<id>`.

The Docker image uses a Node build stage to run the frontend build, then copies only `web/dist` into the Python runtime image. Runtime containers do not require Node. The `prototype/` directory is only a static visual and interaction reference and is not part of the production build.

`WEBUI_HOST` and `WEBUI_PORT` control the WebUI/API listener. This project does not include an Nginx, HTTPS, or reverse-proxy production scheme in v1.

## Bootstrap configuration

Required startup env:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | Database connection string used before any runtime configuration can be loaded. |
| `SETTINGS_ENCRYPTION_KEY` | Stable key used to encrypt/decrypt stored Bot tokens and LLM API keys. |
| `WEBUI_ADMIN_TOKEN` | Single WebUI bearer token. |
| `WEBUI_HOST` | WebUI/API listen host. |
| `WEBUI_PORT` | WebUI/API listen port. |

Bot token, owner ID, LLM API key, provider model, summary profile, and group summary settings are database-managed runtime configuration. Do not treat legacy `.env` values for those fields as the long-term source of truth.

Generate `SETTINGS_ENCRYPTION_KEY` with:

```bash
python3 -c "from summary_relay_bot.services.secrets import SecretService; print(SecretService.generate_key())"
```

## Delivery mode

V1 uses Telegram Bot API polling. Webhook delivery is out of scope. Startup checks Telegram webhook state and fails closed when a webhook URL is active unless `ALLOW_WEBHOOK_DELETE=true` is set. Pending updates are preserved by default when webhook deletion is explicitly enabled.

## Administrator commands

Administrator commands are effective only in the administrator's private chat with the bot.

- `/groups` lists discovered groups.
- `/enable_group <chat_id> [interval_minutes]` enables scheduled summaries.
- `/disable_group <chat_id>` disables scheduled summaries.
- `/set_interval <chat_id> <interval_minutes>` updates an enabled group's schedule.
- `/summary` summarizes enabled groups manually.
- `/summary <chat_id>` summarizes one known group manually.
- `/reply <user_id> <message>` sends plain text to a known private user.

Command menu scopes are only a visibility aid. Every handler still checks the configured owner ID and private chat context server-side.

## Summary behavior

Each group has an independent internal sequence cursor. A summary job reads messages after the last successful cursor, calls the configured LLM, sends the summary privately to the administrator, and advances the cursor only after Telegram delivery succeeds. LLM failures, timeouts, empty output, and Telegram delivery failures leave the cursor unchanged.

Scheduled and manual summaries share the same summary service and per-group running lease. Scheduler coalescing and `max_instances=1` are local protections; the database running-job constraint is the cross-process safety boundary for v1.

## Private relay behavior

When a non-admin private user messages the bot:

1. The raw update is stored.
2. Private-user and private-message metadata are stored.
3. The administrator receives an info card.
4. The original message is copied with `copyMessage` when Telegram supports it.
5. Successful administrator-side message IDs are mapped back to the private user.

If copying fails, the bot records the failure and notifies the administrator. The service does not download and re-upload protected Telegram content.

Administrator replies are routed only by reply maps. Unscoped ordinary administrator messages are rejected instead of guessed from recent activity.

## Retention

`RAW_UPDATE_RETENTION_DAYS` defaults to 30. The in-process scheduler runs a daily raw-update retention cleanup job. Cleanup redacts old raw update JSON payload bodies only. It preserves private users, private messages, reply maps, summary state, summary jobs, summary results, and raw update audit/status fields.

## Post-launch verification

1. Have the administrator send `/start` privately and confirm the bot replies.
2. Send a test message in a group, then run `/groups` privately and confirm the group is discovered but disabled.
3. Enable one group with `/enable_group <chat_id> <minutes>`, send a group test message, and run `/summary <chat_id>` privately.
4. Have a non-admin private user message the bot, confirm the administrator receives an info card and copied message, then reply to the mapped message.
5. Inspect retention by running the scheduled job or `cleanup_raw_update_payloads` in an operational shell against non-production test data before relying on it for production cleanup.

## Logging and secrets

Normal logs must not include bot tokens, database passwords, `SETTINGS_ENCRYPTION_KEY`, `WEBUI_ADMIN_TOKEN`, LLM API keys, raw update JSON, private relay content, Telegram numeric IDs, file IDs, full prompt bodies, or raw provider responses. Configuration rendering uses redacted values for secrets.

Secret handling boundaries:

- Bot tokens and LLM API keys are encrypted before database persistence.
- API responses, logs, exceptions, and audit records must remain redacted.
- The WebUI supports replacing secrets but does not support viewing plaintext secret values.
- Empty secret inputs mean "do not modify"; non-empty secret inputs replace the stored encrypted value.

## Restart semantics

`needs_restart` indicates that a database change has not been loaded by the currently running Telegram polling process.

Restart required:

- Bot token replacement.
- Owner ID change.
- Enabling a different Bot instance.

Restart not required:

- LLM Provider edits.
- Summary Profile edits.
- Group summary settings edits.

## Troubleshooting

- **No polling updates:** check for an active webhook and ensure only one polling process is running.
- **WebUI starts but polling does not:** confirm that an enabled Bot instance exists, its token decrypts with the current `SETTINGS_ENCRYPTION_KEY`, and restart after Bot token, owner ID, or enabled Bot changes.
- **No group messages:** check BotFather privacy mode and whether the bot was re-added after privacy changes.
- **Summaries fail without cursor movement:** inspect `summary_jobs.error_type` and `error_message`; this is expected for LLM or delivery failures.
- **Private relay cannot notify admin:** confirm the administrator has started the bot and has not blocked it.
- **Reply rejected as unmapped:** reply directly to the info card or copied message, or use `/reply` for a known private user.
