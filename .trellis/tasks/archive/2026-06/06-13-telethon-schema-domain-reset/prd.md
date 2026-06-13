# Schema and domain table reset

## Goal

Create a clean fresh-database schema for the refactored private relay and group summary domains without preserving old development data.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- Use one application database.
- Do not implement legacy data migration from the current development schema.
- Initialize domain-oriented tables for private relay, summary userbot configuration, summary groups, summary messages, summary jobs/results, and delivery attempts.
- Preserve existing LLM Provider and Summary Profile tables/configuration behavior unless a schema adjustment is required for summary groups to reference them.
- Include ownership and extension fields needed by later child tasks, including `userbot_id`, Telegram entity type, Telegram message id/date/edit/delete metadata, and future channel/backfill support.
- Keep secret-bearing columns clearly scoped for encryption by service code.

## Acceptance Criteria

- [ ] Empty database initialization creates the new relay and summary-domain tables.
- [ ] Old development data is not required or migrated.
- [ ] Summary group/message tables include `userbot_id` and Telegram source identifiers needed for future multi-userbot and backfill support.
- [ ] Summary entity schema reserves entity type information for future broadcast channel support while first-version collection can limit to groups/megagroups.
- [ ] Summary delivery attempt schema can record async notification status, retry count, timeout/failure, target relay bot, and chunk metadata when needed.
- [ ] Existing LLM Provider and Summary Profile tests still pass or are updated only for required schema integration.
- [ ] Documentation or migration notes clearly state that existing development data must be reset/recreated.

## Notes

- This child should be implemented before other children that depend on new tables.
