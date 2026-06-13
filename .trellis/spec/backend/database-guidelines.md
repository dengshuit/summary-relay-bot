# Database Guidelines

> Database patterns and conventions for this project.

---

## Overview

The project uses SQLAlchemy asyncio with Alembic migrations. Runtime code must assume the schema has already been migrated before the application starts.

---

## Query Patterns

<!-- How should queries be written? Batch operations? -->

(To be filled by the team)

---

## Migrations

### Scenario: Docker Compose startup migrations

#### 1. Scope / Trigger

- Trigger: Docker Compose startup for the `bot` service.
- Reason: The application loads database-managed runtime configuration during startup. On a fresh database, querying tables such as `bot_instances` before migrations causes `UndefinedTableError`.

#### 2. Signatures

- Docker Compose service command:
  ```yaml
  command: ["sh", "-c", "alembic upgrade head && exec summary-relay-bot"]
  ```
- Non-Compose migration command:
  ```bash
  alembic upgrade head
  ```

#### 3. Contracts

- `DATABASE_URL` must point to the target database before migrations run.
- `alembic upgrade head` must complete successfully before `summary-relay-bot` starts.
- Empty migrated databases are valid. They should start WebUI with no Telegram polling until an enabled Bot instance exists.

#### 4. Validation & Error Matrix

- Missing/invalid `DATABASE_URL` -> Alembic fails; bot application must not start.
- Fresh database -> Alembic creates schema; bot starts and reports `no_enabled_bot` when no Bot instance is enabled.
- Already migrated database -> Alembic is a no-op or applies pending migrations; bot starts.
- Migration failure -> container exits before `summary-relay-bot` runs.

#### 5. Good/Base/Bad Cases

- Good: `docker compose up -d` on a fresh database migrates schema and starts WebUI.
- Base: `docker compose up -d bot` on an existing database applies pending migrations and starts.
- Bad: starting `summary-relay-bot` directly in Compose before migrations, producing `relation "bot_instances" does not exist`.

#### 6. Tests Required

- Unit tests should cover startup behavior on an empty migrated database.
- Deployment checks should run `docker compose config` when Docker is available.
- Manual smoke test for release: fresh Postgres data directory plus `docker compose up -d` should not log `UndefinedTableError` for application tables.

#### 7. Wrong vs Correct

##### Wrong

```yaml
command: ["summary-relay-bot"]
```

##### Correct

```yaml
command: ["sh", "-c", "alembic upgrade head && exec summary-relay-bot"]
```

---

## Naming Conventions

<!-- Table names, column names, index names -->

(To be filled by the team)

---

## Common Mistakes

### SummaryEntity compatibility aliases are not relationships

After the Telethon schema reset, `GroupChat` and `GroupSummarySettings` are
compatibility aliases for `SummaryEntity`. `SummaryEntity.summary_settings` is
a Python property, not an ORM relationship or a separate table.

Do not join `GroupChat` to `GroupSummarySettings`; SQLAlchemy treats that as a
self-join of the same mapped class and cannot infer the join side without an
explicit alias. For group summary settings filters, use the direct
`SummaryEntity` columns through `GroupChat`.

#### Wrong

```python
select(GroupChat).outerjoin(GroupSummarySettings, GroupSummarySettings.group_id == GroupChat.id)
```

#### Correct

```python
select(GroupChat).where(GroupChat.enabled.is_(True))
select(GroupChat).where(GroupChat.summary_profile_id == profile_id)
```

Tests must not assert that `select(GroupSummarySettings)` is empty to prove no
settings row exists. That query now selects summary entities. Instead, assert
the entity-level settings contract directly:

```python
assert group.summary_settings is None
assert group.enabled is False
assert group.interval_minutes is None
assert group.summary_profile_id is None
```

Service helpers that expose optional settings must also apply this contract
explicitly. Fetching the entity by id is not enough because it returns the
discovered group row even when no summary settings have been configured.

#### Wrong

```python
return await session.scalar(
    select(GroupSummarySettings).where(GroupSummarySettings.id == group.id)
)
```

#### Correct

```python
settings = await session.scalar(
    select(GroupSummarySettings).where(GroupSummarySettings.id == group.id)
)
return settings.summary_settings if settings is not None else None
```
