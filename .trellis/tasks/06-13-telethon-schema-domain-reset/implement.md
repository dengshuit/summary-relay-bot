# Schema and domain table reset - Implementation Plan

## Preconditions

- Parent PRD/design are accepted.
- Existing development data preservation is not required.
- No runtime behavior should be implemented in this child unless required to keep model/schema tests meaningful.

## Checklist

1. Review current model and migration usage.
   - `src/summary_relay_bot/db/models.py`
   - `migrations/versions/*`
   - table references in repositories/services/tests

2. Decide the Alembic baseline shape.
   - Prefer a fresh baseline that creates the final schema directly.
   - Do not add data migration or old-table transform logic.
   - Ensure `alembic upgrade head` works on an empty database.
   - If the new baseline includes `llm_providers.models`, make any later LLM-model migration a no-op or remove its duplicate add-column behavior so the chain remains valid.

3. Update SQLAlchemy models.
   - Add relay-domain models.
   - Add summary userbot/auth-session models.
   - Add summary entity/message/state/job/result/delivery-attempt models.
   - Keep LLM Provider, Summary Profile, and Audit Log models usable.
   - Remove or clearly replace old global raw update / group / bot instance concepts.
   - Add only the minimum temporary compatibility aliases/properties required to keep existing imports and targeted tests working until later child tasks move service code fully to the new names.
   - Record any temporary aliases in task notes or code comments so later children can remove them deliberately.

4. Update migrations.
   - Create fresh schema definitions for all current tables.
   - Include JSON/JSONB variants consistently with existing migration style.
   - Include partial unique indexes for one enabled relay bot, one enabled userbot, one default summary profile, and one active summary job per entity.
   - Include check constraints for statuses and trigger/direction fields.
   - Include the FK, default, nullable, and `ondelete` contracts from `design.md`; do not leave disabled/default behavior only to services.
   - Replace `group_summary_settings` references with `summary_entities.summary_profile_id` / entity settings fields for this schema baseline.

5. Update minimal tests/fixtures for schema initialization.
   - Adjust `tests/unit/test_models.py` and persistence tests that assert table shape.
   - Keep LLM Provider/Profile model tests aligned with existing behavior.
   - Add model-level tests for key constraints where practical.
   - Add or update tests that prove `summary_entities` default to disabled, entity type metadata is available through the entity/message relationship, one enabled userbot is enforced, and summary delivery attempts link to results/relay bots.
   - Update Summary Profile delete-conflict tests only as far as needed for the new schema reference path.

6. Update docs note for schema reset if this child owns the first documentation touch.
   - State existing development DB data is not preserved.
   - State users should recreate/reset DB before using this refactor.
   - If full README rewrite is deferred to the final integration child, add a concise schema reset note now and leave detailed Telethon/userbot operational docs to the final child.

## Validation Commands

Run the narrowest useful checks for this child:

```bash
python3 -m compileall -q src tests migrations
python3 -m pytest tests/unit/test_models.py -q
python3 -m pytest tests/integration/test_persistence.py -q
tmp_db="$(mktemp -u /tmp/summary-relay-schema-XXXXXX.db)" && DATABASE_URL="sqlite+aiosqlite:///$tmp_db" alembic upgrade head
```

The Alembic empty-database check is mandatory for this child because the normal test fixture uses `Base.metadata.create_all` and does not validate migration order.

Also run a small import smoke if compile/tests do not exercise mapper configuration:

```bash
python3 -c "from summary_relay_bot.db import models; print(len(models.Base.metadata.tables))"
```

## Risk Areas

- Existing tests and services import old model names extensively. Keep the child scoped, but do not leave core imports broken at completion.
- Temporary compatibility aliases can keep this child independently verifiable, but they must point at the new table ownership and must not reintroduce old tables.
- Partial unique indexes must support both SQLite test DB and PostgreSQL production DB.
- JSON columns must keep the existing PostgreSQL JSONB plus SQLite JSON variant pattern.
- Secret columns must be encrypted by services later; schema names should make secret boundaries obvious.
- Removing `telegram_updates` affects private relay tests and raw update retention code; this child should either adjust or delete obsolete retention/raw-update model tests as part of the schema reset.
- Summary Profile references move from `group_summary_settings` to `summary_entities`; profile delete-conflict logic/tests must not silently allow deleting a profile used by summary entities.

## Completion Criteria

- Fresh schema is represented in SQLAlchemy models and Alembic migrations.
- Empty database initialization works.
- Model/schema tests pass or are updated to the new domain model.
- Core imports and mapper configuration are not broken.
- No legacy data migration path is implied.
