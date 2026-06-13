# Schema and domain table reset - Design

## Scope

This child task defines and initializes the fresh database schema for the refactored architecture. It does not implement runtime behavior, Telethon login, ingestion, summary jobs, notification delivery, or WebUI pages beyond what is required to keep model imports and schema tests coherent.

The project is still pre-production. Existing development data does not need migration. Empty-database initialization is the target.

## Migration Strategy

Use a fresh schema baseline rather than compatibility migrations:

- The final migration chain must create the new tables correctly from an empty database.
- Do not write data-copy, transform, or legacy-table migration logic.
- Existing development databases must be recreated/reset outside the app before using this refactor.
- Keep Alembic consistent for `alembic upgrade head` on an empty database.

Implementation may rewrite the current initial migration files into a fresh baseline, or collapse them into a new baseline revision, as long as fresh initialization is deterministic and legacy data migration is not implied.

## Table Groups

## Hard Schema Contracts

This child must leave the repository importable after the schema reset. Runtime behavior can still be completed by later children, but `python3 -m compileall -q src tests migrations` and the targeted model/persistence tests must pass.

Shared implementation contracts:

- JSON columns use the existing PostgreSQL `JSONB` plus SQLite `JSON` variant pattern.
- Secret-bearing columns use explicit `_encrypted` names and are never represented by plaintext response fields in later API schemas.
- `created_at` and `updated_at` columns are non-null where listed. ORM defaults may use `utcnow`; migration columns must be nullable-safe for empty-database initialization.
- Partial unique indexes must work on SQLite test databases and PostgreSQL deployments.
- Status/enum-like fields use check constraints in models and migrations when values are known in this task.
- Message entity type is not duplicated on every `summary_messages` row in this child. It is derived through `summary_messages.entity_id -> summary_entities.entity_type`; tests should verify this join path.

Foreign-key and default contracts that must not be left to later service code:

| Table | Required defaults and constraints |
| --- | --- |
| `relay_bots` | `enabled=false`, `status='unvalidated'`, `needs_restart=false`, one enabled row partial unique index. |
| `relay_private_users` | unique `telegram_user_id`. |
| `relay_private_messages` | FK `private_user_id -> relay_private_users.id` cascade; `direction in ('incoming', 'outgoing')`; optional unique dedupe on non-null `telegram_update_id` if the implementation keeps Bot API update IDs. |
| `relay_reply_maps` | FK `private_user_id` cascade; FK `private_message_id` set null; unique `(owner_chat_id, owner_message_id)`; `status in ('mapping_pending', 'mapped', 'mapping_failed')`. |
| `summary_userbots` | `enabled=false`, `auth_status='unconfigured'`, `runtime_status='stopped'`, one enabled row partial unique index. |
| `summary_userbot_auth_sessions` | FK `userbot_id -> summary_userbots.id` cascade; `status in ('code_sent', 'password_required', 'completed', 'expired', 'failed')`; non-null `expires_at`. |
| `summary_entities` | FK `userbot_id -> summary_userbots.id` cascade; unique `(userbot_id, telegram_entity_id)`; `enabled=false`; `collection_status='disabled'`; `entity_type in ('group', 'supergroup', 'megagroup', 'broadcast_channel', 'unknown')`; `summary_profile_id -> summary_profiles.id` set null; `interval_minutes` nullable until configured. |
| `summary_messages` | FK `entity_id -> summary_entities.id` cascade; FK `userbot_id -> summary_userbots.id` cascade; unique `(entity_id, telegram_message_id)`; indexed `(entity_id, id)` and `(entity_id, message_date)`; `source_kind in ('telethon_update', 'future_backfill')`; no raw Telethon event payload column. |
| `summary_states` | FK `entity_id -> summary_entities.id` cascade; unique `entity_id`; `last_summary_sequence=0`. |
| `summary_jobs` | FK `entity_id -> summary_entities.id` cascade; provider/profile FKs set null; `trigger_type in ('manual', 'scheduled')`; `status in ('pending', 'running', 'succeeded', 'failed', 'blocked')`; one active pending/running job per entity partial unique index. |
| `summary_results` | FK `job_id -> summary_jobs.id` cascade and unique; FK `entity_id -> summary_entities.id` cascade; provider/profile FKs set null; no Telegram delivery columns. |
| `summary_delivery_attempts` | FK `summary_result_id -> summary_results.id` cascade; FK `relay_bot_id -> relay_bots.id` set null; status check; chunk/message metadata stored as ordered JSON. |

### Shared Tables Kept

Keep the current LLM and audit concepts:

- `llm_providers`
- `summary_profiles`
- `audit_logs`

`summary_profiles` remain the configuration referenced by summary entities/jobs/results. `llm_providers.models` remains part of the baseline schema.

### Relay Domain

Rename/reframe the current bot/private relay tables into relay-owned tables.

#### `relay_bots`

Purpose: Bot API / aiogram private relay runtime configuration.

Key fields:

- `id`
- `name`
- `bot_token_encrypted`
- `owner_id`
- `telegram_bot_id`
- `telegram_username`
- `enabled`
- `status`: `unvalidated`, `valid`, `invalid`, `error`
- `needs_restart`
- `last_validated_at`
- `created_at`, `updated_at`

Constraints:

- at most one enabled relay bot in the first implementation
- token remains encrypted and never exposed

#### `relay_private_users`

Purpose: users who privately message the relay bot.

Key fields:

- `id`
- `telegram_user_id`
- `username`
- `first_name`
- `last_name`
- `language_code`
- `first_seen_at`, `last_seen_at`

Constraints:

- unique `telegram_user_id`

#### `relay_private_messages`

Purpose: normalized private relay message records.

Key fields:

- `id`
- `private_user_id`
- `direction`: `incoming`, `outgoing`
- `telegram_update_id` nullable, for incoming Bot API deduplication/debug status without storing full raw update payload
- `telegram_chat_id`
- `telegram_message_id`
- `owner_chat_id`
- `owner_message_id`
- `message_type`
- `text`
- `caption`
- `delivery_status`
- `error_type`
- `error_message`
- `created_at`

Constraints:

- private-user FK cascade
- optional unique dedupe over `telegram_update_id` when present

#### `relay_reply_maps`

Purpose: map owner-side message IDs to private users/messages for reply routing.

Key fields:

- `id`
- `private_user_id`
- `private_message_id`
- `owner_chat_id`
- `owner_message_id`
- `source_kind`
- `status`: `mapping_pending`, `mapped`, `mapping_failed`
- `created_at`

Constraints:

- unique `(owner_chat_id, owner_message_id)`

### Summary Userbot Domain

#### `summary_userbots`

Purpose: one enabled Telethon userbot configuration and authorization state.

Key fields:

- `id`
- `name`
- `api_id`
- `api_hash_encrypted`
- `phone_number_encrypted`
- `session_encrypted`
- `proxy_url_encrypted`
- `telegram_user_id`
- `telegram_username`
- `telegram_display_name`
- `enabled`
- `auth_status`: `unconfigured`, `code_sent`, `password_required`, `authorized`, `revoked`, `error`
- `runtime_status`: `stopped`, `starting`, `running`, `reloading`, `failed`, `disabled`
- `last_authorized_at`
- `last_started_at`
- `last_stopped_at`
- `last_error_type`
- `last_error_message`
- `created_at`, `updated_at`

Constraints:

- at most one enabled userbot in the first implementation
- secrets are encrypted and never returned in API responses

#### `summary_userbot_auth_sessions`

Purpose: transient WebUI login flow state between "send code" and "submit code/2FA".

Key fields:

- `id`
- `userbot_id`
- `phone_code_hash_encrypted`
- `status`: `code_sent`, `password_required`, `completed`, `expired`, `failed`
- `expires_at`
- `last_error_type`
- `last_error_message`
- `created_at`, `updated_at`

Constraints:

- FK to `summary_userbots`
- expired sessions may be cleaned by service code later

### Summary Entity and Message Domain

#### `summary_entities`

Purpose: userbot-visible Telegram conversations that may be enabled for summaries.

Key fields:

- `id`
- `userbot_id`
- `telegram_entity_id`
- `telegram_access_hash` nullable, stored only if implementation needs it
- `telegram_peer_type`: `chat`, `channel`, `user`, or Telethon-derived peer type
- `entity_type`: `group`, `supergroup`, `megagroup`, `broadcast_channel`, `unknown`
- `title`
- `username`
- `enabled`
- `collection_status`: `disabled`, `active`, `paused`, `error`
- `summary_profile_id`
- `interval_minutes`
- `timezone`
- `discovered_at`
- `last_seen_at`
- `last_refreshed_at`
- `last_error_type`
- `last_error_message`
- `created_at`, `updated_at`

Constraints:

- unique `(userbot_id, telegram_entity_id)`
- `enabled` defaults to `false`
- `collection_status` defaults to `disabled`
- `summary_profile_id` is nullable and uses `SET NULL`; a null value means "use the current default Summary Profile" in later service/API code
- `interval_minutes` is nullable while a discovered entity is not configured for scheduled summaries
- first implementation enables collection only for `group`, `supergroup`, `megagroup`
- broadcast channels may be discovered but not collected/summarized in first implementation

#### `summary_messages`

Purpose: normalized group messages for summarization.

Key fields:

- `id`
- `entity_id`
- `userbot_id`
- `telegram_message_id`
- `telegram_thread_id` nullable, reserved for future topics/threads
- `source_kind`: `telethon_update`, `future_backfill`
- `message_date`
- `edited_at`
- `deleted_at`
- `collected_at`
- `edited_after_summary_at`
- `sender_user_id`
- `sender_username`
- `sender_display_name`
- `message_type`
- `text`
- `caption`
- `summary_content`
- `file_name`
- `mime_type`
- `file_size`
- `media_metadata`

Constraints/indexes:

- unique `(entity_id, telegram_message_id)`
- index `(entity_id, id)` for summary cursor reads
- index `(entity_id, message_date)` for future backfill/window work
- entity type is derived by joining `summary_entities`; do not add a redundant message-level entity type field unless a later child proves it is needed

The table does not store full Telethon raw event dictionaries or full MTProto payloads.

### Summary Job Domain

#### `summary_states`

Purpose: per-entity cursor.

Key fields:

- `id`
- `entity_id`
- `last_summary_sequence`
- `last_summary_at`
- `updated_at`

Constraints:

- unique `entity_id`

`last_summary_sequence` points at `summary_messages.id`, preserving the existing local-sequence cursor shape.

#### `summary_jobs`

Purpose: manual/scheduled summary job state.

Key fields:

- `id`
- `entity_id`
- `trigger_type`: `manual`, `scheduled`
- `status`: `pending`, `running`, `succeeded`, `failed`, `blocked`
- `starting_sequence`
- `cutoff_sequence`
- `prompt_version`
- `llm_provider_id`
- `summary_profile_id`
- `model`
- `lease_expires_at`
- `error_type`
- `error_message`
- `created_at`, `started_at`, `finished_at`

Constraints:

- at most one active pending/running job per entity
- provider/profile references use `SET NULL` for historical readability

#### `summary_results`

Purpose: authoritative persisted summary content.

Key fields:

- `id`
- `job_id`
- `entity_id`
- `summary_text`
- `prompt_version`
- `llm_provider_id`
- `summary_profile_id`
- `model`
- `interval_start_sequence`
- `interval_end_sequence`
- `created_at`

Constraints:

- unique `job_id`

Telegram delivery fields do not belong here; delivery is separate.

#### `summary_delivery_attempts`

Purpose: asynchronous private-relay notification tracking.

Key fields:

- `id`
- `summary_result_id`
- `relay_bot_id`
- `target_chat_id`
- `status`: `pending`, `running`, `succeeded`, `failed`, `skipped`, `timeout`
- `attempt_count`
- `max_attempts`
- `timeout_seconds`
- `total_chunks`
- `sent_chunks`
- `telegram_message_ids`
- `error_type`
- `error_message`
- `created_at`, `started_at`, `finished_at`, `updated_at`

Constraints:

- FK to `summary_results`
- FK to `relay_bots` nullable, because summary generation can succeed without an available relay bot
- `max_attempts` means total attempts, not retry count; later delivery code must use `3` for initial attempt plus two retries
- `telegram_message_ids` stores ordered chunk delivery metadata, for example a JSON array of owner-side Telegram message IDs in chunk order
- `total_chunks` and `sent_chunks` are non-negative integers; partial chunk success remains visible without changing summary result persistence

## Removed or Replaced Concepts

- `telegram_updates`: remove as a shared raw update table. First-version schema stores normalized private relay and summary records only.
- `groups` / `group_messages`: replaced by `summary_entities` / `summary_messages`.
- `group_summary_settings`: replaced by summary entity settings fields on `summary_entities` in this child. Later service/API code must update Summary Profile delete-conflict checks to count `summary_entities.summary_profile_id`.
- `bot_instances`: replaced by `relay_bots`.
- generic `delivery_attempts`: replaced by domain-specific private relay delivery fields and `summary_delivery_attempts`.

## Compatibility Notes

Code using old model names will be updated incrementally across later child tasks, but this child must not leave the repository broadly broken. At completion:

- Core package imports and compile checks must pass.
- Targeted schema/model/persistence tests must pass.
- If a later child will own a service rename, this child may add temporary Python aliases or compatibility properties only when they point at the new domain-owned tables and do not recreate old tables.
- Temporary aliases must be named in code or task notes so later child tasks can remove them while moving service code to new domain names.
- App import smoke must be covered by the compile check or an explicit import command; `compileall` alone is not enough for SQLAlchemy mapper configuration, so targeted tests must instantiate metadata/session fixtures.

## Migration Chain Contract

Use a fresh empty-database baseline. The implementation may collapse the existing migration chain into one baseline plus no-op compatibility revisions, or rewrite both current revisions consistently. It must not create a chain where a later revision re-adds a column already present in the new baseline.

The child completion gate must include an explicit Alembic empty-database check using SQLite unless a PostgreSQL test database is already available:

```bash
tmp_db="$(mktemp -u /tmp/summary-relay-schema-XXXXXX.db)"
DATABASE_URL="sqlite+aiosqlite:///$tmp_db" alembic upgrade head
```

This validates the migration chain separately from `Base.metadata.create_all`.
