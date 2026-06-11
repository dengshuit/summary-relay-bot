# Improve Docker First Boot And Log Timestamps

## Goal

Make the production Docker Compose deployment usable with a single `docker compose up -d` on a fresh database, and make application logs include timestamps when viewed through `docker logs` / `docker compose logs`.

## What I Already Know

* Current first boot fails on a fresh database until `alembic upgrade head` is run manually.
* The observed failure is `relation "bot_instances" does not exist` during startup when the app tries to load the enabled bot instance.
* The app is expected to start WebUI on an empty migrated database with `no_enabled_bot`; Bot runtime data is configured later through WebUI.
* `docker-compose.yml` starts `bot` after Postgres is healthy but does not run migrations.
* `Dockerfile` uses `CMD ["summary-relay-bot"]`.
* `src/summary_relay_bot/main.py` currently initializes logging with `logging.basicConfig(level=logging.INFO)`, which does not include timestamps in application logs.

## Assumptions

* Automatic startup migrations are acceptable for this single-service deployment.
* If migrations fail, the bot container should fail fast instead of starting against an invalid schema.
* The solution should avoid adding new dependencies.

## Requirements

* `docker compose up -d` must run database migrations before starting the bot application.
* Startup migration behavior must be idempotent for already migrated databases.
* Fresh empty databases must start WebUI successfully after automatic migrations.
* Empty databases with no enabled bot must log `no_enabled_bot` instead of failing on missing tables.
* Application logs must include timestamps by default when viewed through Docker logs.
* Uvicorn logs should follow the same timestamped logging behavior where practical.
* Documentation should no longer imply manual migration is required for the default Docker Compose first boot path.

## Acceptance Criteria

* [ ] With a fresh Postgres data directory, `docker compose up -d` creates schema and starts the WebUI. Not run in this environment because Docker CLI is unavailable.
* [ ] `docker compose logs bot` does not show `relation "bot_instances" does not exist` during first boot. Covered by startup command review; not run in Docker here.
* [x] `docker compose logs bot` shows timestamped application log lines.
* [x] Migration failure prevents the bot app from starting.
* [x] Existing local validation commands pass for the touched backend/deployment files.

## Definition Of Done

* Tests added or updated where appropriate.
* Relevant compile/type/lint validation runs successfully, or limitations are documented.
* README / operations docs updated for the new Docker startup behavior.
* Changes stay scoped to Docker startup, logging setup, and related docs/tests.

## Out Of Scope

* Automatically creating Bot instances or inserting business runtime data.
* Replacing Alembic or changing migration strategy outside startup execution.
* Introducing a separate migration container or orchestrator-specific job.
* Changing secrets/bootstrap configuration behavior.

## Technical Notes

* `docker-compose.yml` currently has `depends_on.postgres.condition: service_healthy` and `restart: unless-stopped`.
* `README.zh-CN.md` and `README.md` currently document manual `docker compose run --rm bot alembic upgrade head`.
* `src/summary_relay_bot/main.py` creates `uvicorn.Config` without a custom log config.
* Candidate minimal implementation:
  * Add a container startup command that runs `alembic upgrade head && exec summary-relay-bot`.
  * Add a `configure_logging()` helper in `main.py` with timestamped format.
  * Set `uvicorn.Config(..., log_config=None)` so Uvicorn does not replace the configured logging.
