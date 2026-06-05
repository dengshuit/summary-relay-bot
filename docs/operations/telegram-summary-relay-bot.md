# Telegram Summary Relay Bot Operations

## Startup checklist

1. Create a Telegram bot with BotFather and set `BOT_TOKEN`.
2. Set the single administrator's numeric Telegram user ID as `OWNER_ID`.
3. Create the PostgreSQL database and run `alembic upgrade head`.
4. Ensure no webhook is configured for this bot token before starting polling.
5. Have the administrator send `/start` to the bot privately.
6. Add the bot to groups that should be collected.
7. If ordinary group messages are not received, review BotFather privacy mode and re-add the bot after changing it.
8. Run exactly one polling process for one bot token.

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

Command menu scopes are only a visibility aid. Every handler still checks `OWNER_ID` and private chat context server-side.

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

Normal logs must not include bot tokens, database passwords, LLM API keys, raw update JSON, private relay content, Telegram numeric IDs, file IDs, full prompt bodies, or raw provider responses. Configuration rendering uses redacted values for secrets.

## Troubleshooting

- **No polling updates:** check for an active webhook and ensure only one polling process is running.
- **No group messages:** check BotFather privacy mode and whether the bot was re-added after privacy changes.
- **Summaries fail without cursor movement:** inspect `summary_jobs.error_type` and `error_message`; this is expected for LLM or delivery failures.
- **Private relay cannot notify admin:** confirm the administrator has started the bot and has not blocked it.
- **Reply rejected as unmapped:** reply directly to the info card or copied message, or use `/reply` for a known private user.
