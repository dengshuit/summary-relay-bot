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

<!-- Database-related mistakes your team has made -->

(To be filled by the team)
