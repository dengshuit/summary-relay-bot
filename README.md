# Telegram Summary Relay Bot

[中文文档](README.zh-CN.md)

Personal Telegram bot that quietly watches group chats, sends private incremental summaries to one administrator, and relays private user messages through the bot so the administrator can reply without exposing a personal account.

This is a v1 polling-based service. It intentionally keeps webhooks, multiple administrators, Redis queues, dashboards, group-public summaries, media transcription, and media file-body storage out of scope.

## Features

- Telegram Bot API polling; no public webhook endpoint required for v1
- Single configured administrator (`OWNER_ID`) with server-side authorization on every admin action
- Group and supergroup discovery by Telegram `chat_id`
- Quiet group collection by default; groups are discovered disabled until explicitly enabled
- Group media represented for summaries with placeholders such as `[photo]`, `[voice]`, `[document: filename]`, `[video]`, and `[sticker]`
- Private incremental summaries for enabled groups
- Summary cursors advance only after both LLM generation and private Telegram delivery succeed
- Manual summaries with `/summary` and `/summary <chat_id>`
- Scheduled summaries with per-group intervals
- Private-user relay with administrator info cards, Telegram `copyMessage`, and reply mappings
- Administrator replies routed by mapped message replies or `/reply <user_id> <message>`
- PostgreSQL-backed metadata, raw update persistence, summary jobs/results, and delivery attempts
- Configurable raw update payload retention that redacts old raw JSON payloads without deleting business metadata
- Privacy-aware Anthropic summary client with whitelisted LLM payload fields and prompt caching

## Requirements

- Python 3.12+
- PostgreSQL 16+
- Docker and Docker Compose for container deployment
- Telegram bot token from BotFather
- Administrator Telegram numeric user ID
- Anthropic API key for group summaries

## Configuration

Copy `.env.example` to `.env` and fill in safe local or production values.

```bash
cp .env.example .env
```

Required variables:

| Variable | Description |
| --- | --- |
| `BOT_TOKEN` | Telegram Bot API token from BotFather. |
| `OWNER_ID` | Single administrator's Telegram numeric user ID. |
| `DATABASE_URL` | Async SQLAlchemy database URL, for example `postgresql+asyncpg://summary_bot:change-me@postgres:5432/summary_relay_bot`. |
| `LLM_API_KEY` | Anthropic API key used by the summary client. |

Important optional variables:

| Variable | Default | Description |
| --- | --- | --- |
| `ALLOW_WEBHOOK_DELETE` | `false` | When `false`, startup fails if Telegram reports an active webhook. |
| `DROP_PENDING_UPDATES_ON_WEBHOOK_DELETE` | `false` | Keep `false` unless intentionally dropping pending updates while deleting a webhook. |
| `RAW_UPDATE_RETENTION_DAYS` | `30` | Raw update JSON payload retention window. Old payload bodies are redacted only. |
| `SUMMARY_DEFAULT_INTERVAL_MINUTES` | `300` | Default interval used by `/enable_group` when no interval is provided. |
| `SCHEDULER_TIMEZONE` | `UTC` | Scheduler timezone. |
| `SCHEDULER_MISFIRE_GRACE_SECONDS` | `300` | Scheduler misfire grace period. |
| `SCHEDULER_COALESCE` | `true` | Coalesce missed scheduled runs after downtime. |
| `LLM_PROVIDER` | `anthropic` | LLM provider name. V1 ships with the Anthropic client boundary. |
| `LLM_MODEL` | `claude-opus-4-8` | Anthropic model used for summaries. |
| `LLM_TIMEOUT_SECONDS` | `30` | Summary request timeout. |
| `SUMMARY_PROMPT_VERSION` | `v1` | Prompt version stored on summary jobs/results. |

Do not commit real tokens, database passwords, or API keys.

## Production Deployment

Production deployment is centered on the Docker image and `docker-compose.yml`.

### Build and publish the Docker image

The GitHub Actions workflow in `.github/workflows/docker-image.yml` builds the image from `Dockerfile` and publishes it to GitHub Container Registry:

```text
ghcr.io/<owner>/<repo>
```

Workflow behavior:

- Pushes to `main` or `master` build and publish the image.
- Tags matching `v*.*.*` build and publish versioned image tags.
- Pull requests build the image but do not publish it.
- Published tags include branch/tag refs, `sha-<commit>`, and `latest` on the default branch.

The workflow uses GitHub's built-in `GITHUB_TOKEN`; no extra registry secret is required for GHCR in the same repository.

### Configure production environment

Create `.env` on the deployment host:

```bash
cp .env.example .env
```

Set production-safe values for at least:

```env
BOT_TOKEN=replace-with-real-bot-token
OWNER_ID=replace-with-admin-telegram-user-id
DATABASE_URL=postgresql+asyncpg://summary_bot:replace-with-db-password@postgres:5432/summary_relay_bot
LLM_API_KEY=replace-with-real-llm-api-key
POSTGRES_PASSWORD=replace-with-db-password
```

`DATABASE_URL` and `POSTGRES_PASSWORD` must use the same database password when using the bundled PostgreSQL service.

### Start with a published image

After the GitHub Actions workflow publishes an image, set `BOT_IMAGE` to the GHCR image tag:

```bash
export BOT_IMAGE=ghcr.io/<owner>/<repo>:latest
docker compose pull bot
docker compose up -d postgres
docker compose run --rm bot alembic upgrade head
docker compose up -d bot
```

Run exactly one polling process for one bot token. Telegram polling and webhooks are mutually exclusive, so unset any webhook before using polling or set `ALLOW_WEBHOOK_DELETE=true` deliberately.

### Upgrade production

Pull the newer image, run migrations, and restart the bot:

```bash
export BOT_IMAGE=ghcr.io/<owner>/<repo>:latest
docker compose pull bot
docker compose run --rm bot alembic upgrade head
docker compose up -d bot
```

## Development Deployment

Use local Python for fast iteration and Docker Compose when you need a containerized local run.

### Local Python environment

Install the package and development dependencies:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

If your environment does not support `venv`, install into the user environment instead:

```bash
python3 -m pip install --user --break-system-packages -e '.[dev]'
```

Run tests:

```bash
python3 -m pytest -q
```

Run a compile check:

```bash
python3 -m compileall -q src tests migrations
```

Check installed dependency consistency:

```bash
python3 -m pip check
```

### Local Docker Compose

Create and edit `.env`:

```bash
cp .env.example .env
```

Start PostgreSQL:

```bash
docker compose up -d postgres
```

Run database migrations:

```bash
docker compose run --rm bot alembic upgrade head
```

Build and start the bot locally:

```bash
docker compose up --build bot
```

Or start all services after migrations:

```bash
docker compose up --build
```

## Database Migrations

Run migrations before starting the bot against a fresh database:

```bash
alembic upgrade head
```

When using Docker Compose, run migrations through the bot image:

```bash
docker compose run --rm bot alembic upgrade head
```

## Telegram Setup

1. Create a bot with BotFather and set `BOT_TOKEN`.
2. Find the administrator's numeric Telegram user ID and set `OWNER_ID`.
3. Have the administrator send `/start` to the bot privately before expecting summary or relay notifications.
4. Add the bot to groups that should be collected.
5. If ordinary group messages are not received, review BotFather privacy mode and re-add the bot after changing privacy settings.

The bot is quiet in groups by design. Summaries and management responses are sent only in the administrator's private chat.

## Administrator Commands

Administrator commands work only in the administrator's private chat with the bot.

| Command | Description |
| --- | --- |
| `/start` | Show bot status. |
| `/help` | Show administrator help. |
| `/groups` | List discovered groups, enabled state, and interval. |
| `/enable_group <chat_id> [minutes]` | Enable scheduled summaries for a known group. |
| `/disable_group <chat_id>` | Disable scheduled summaries for a group. |
| `/set_interval <chat_id> <minutes>` | Update a group's interval without implicitly enabling it. |
| `/summary` | Manually summarize all enabled groups. |
| `/summary <chat_id>` | Manually summarize one known group. |
| `/reply <user_id> <message>` | Send a text reply to a known private user. |

Command menu scopes are only a visibility aid. Server-side owner and private-chat checks still authorize every admin handler.

## Summary Behavior

Each group has an independent internal sequence cursor.

A summary job:

1. Reads group messages after the last successful cursor.
2. Builds a privacy-filtered LLM payload from `message_type` and `summary_content` only.
3. Calls the configured Anthropic summary client.
4. Sends the generated summary privately to the administrator.
5. Advances the cursor only if Telegram delivery succeeds and the cursor has not changed concurrently.

LLM failures, timeouts, empty output, and Telegram delivery failures leave the cursor unchanged.

Scheduled and manual summaries share the same summary service and cursor logic. APScheduler `coalesce` and `max_instances=1` are local protections; the database running-job constraint is the correctness boundary for overlapping jobs.

## Private Relay Behavior

When a non-admin private user messages the bot:

1. The raw update is stored.
2. Private-user and private-message metadata are stored.
3. The administrator receives an info card.
4. The original message is copied to the administrator with Telegram `copyMessage` when possible.
5. Successful administrator-side message IDs are mapped back to the private user.

If copying fails, the bot records the failure and notifies the administrator. It does not download or re-upload protected Telegram content.

Administrator replies are routed only through reply maps. Unscoped ordinary administrator messages are rejected instead of guessed from recent activity.

## Retention

`RAW_UPDATE_RETENTION_DAYS` defaults to 30. The in-process scheduler runs a daily raw-update retention cleanup job.

Cleanup redacts old raw update JSON payload bodies only. It preserves:

- raw update audit/status fields
- private users
- private messages
- reply maps
- summary state
- summary jobs
- summary results

## Privacy Boundaries

- Raw Telegram update JSON is sensitive and retained only for the configured retention window.
- The service stores media metadata and Telegram file identifiers, but not media file bodies.
- Private relay content is not sent to the LLM.
- Summary LLM payloads are built from a whitelist: message type and summary content.
- Normal logs must not include bot tokens, database passwords, LLM API keys, raw update JSON, private relay content, Telegram numeric IDs, file IDs, full prompt bodies, or raw provider responses.
- Configuration rendering redacts secrets and sensitive numeric identifiers.

## Manual Verification Checklist

Use a test bot and non-production data.

1. Administrator sends `/start` privately and receives a response.
2. Send a test message in a group, then run `/groups` privately and confirm the group is discovered but disabled.
3. Enable one group with `/enable_group <chat_id> <minutes>`.
4. Send group messages and run `/summary <chat_id>` privately.
5. Confirm the administrator receives a summary.
6. Have a non-admin private user message the bot.
7. Confirm the administrator receives an info card and copied message.
8. Reply to the mapped administrator-side message and confirm the private user receives the reply.
9. Test `/reply <user_id> <message>` for a known private user.
10. Confirm an unscoped ordinary administrator message is rejected.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| No polling updates | Ensure no webhook is active and only one polling process is running for the bot token. |
| Group messages are not collected | Check BotFather privacy mode and whether the bot was re-added after changing it. |
| `/groups` does not show a group | Send a new message in that group after the bot has joined and can receive updates. |
| Summary fails but cursor does not move | Inspect `summary_jobs.error_type` and `summary_jobs.error_message`; cursor preservation is expected on failures. |
| Administrator does not receive summaries or relay notifications | Confirm the administrator started the bot privately and has not blocked it. |
| Reply is rejected as unmapped | Reply directly to the info card or copied message, wait briefly for mapping persistence, or use `/reply` for a known user. |

## Scope Boundaries

Deferred from v1:

- Multiple administrators, roles, or tenant boundaries
- Webhook delivery
- Redis queues or horizontal workers
- Web dashboard or non-Telegram management UI
- Media understanding such as OCR, image analysis, or voice transcription
- Downloading or storing Telegram media file bodies
- Current-chat mode for replies
- Public group summary publication
