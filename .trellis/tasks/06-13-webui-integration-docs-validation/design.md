# WebUI integration docs and validation - Design

## Scope

This child finishes the integrated user-facing surface for the Telethon group
summary refactor:

- confirm WebUI navigation separates private relay bot configuration, Telethon
  userbot authorization, groups, summaries, private relays, providers, and
  profiles
- expose summary notification delivery status in summary/job UI where summary
  results are inspected
- update operations documentation for schema reset, Telethon credentials,
  session secrecy, proxy requirements, no historical backfill, and the new
  summary cursor/delivery ordering
- run final cross-child validation

It does not introduce new backend summary behavior; implementation children
already own auth, discovery/ingestion, summary persistence, and bounded
delivery.

## WebUI Contract

Existing pages:

- `Bot`: private relay Bot API configuration
- `Userbot`: Telethon userbot credentials/auth flow
- `Groups`: group discovery refresh and group list
- `GroupDetail`: enablement, summary settings, manual production summary, test
  summary, job polling
- `Summaries`: historical summary/result inspection
- `PrivateRelays`: private relay conversation/delivery inspection
- `Engine`: LLM providers and summary profiles

Delivery metadata is available through API `delivery` fields on summary job
result and historical summaries. Display should use compact status badges and
avoid raw owner/chat ids.

## Documentation Contract

Update README files to state:

- development schema reset does not preserve old development data
- Telethon userbot needs `api_id` and secret `api_hash` from `my.telegram.org`
- the userbot `StringSession` is account-bearing secret material
- SOCKS proxy support requires `python-socks[asyncio]`
- first version discovers visible groups and collects only update-stream
  messages after startup/reconnect; no `iter_messages` / `get_messages`
  historical backfill
- summaries persist results and advance cursor after LLM/result success
- relay notification is asynchronous/bounded and does not control summary job
  success

## Validation

Final validation should combine focused backend suites from each child plus
frontend typecheck/build. Full repository exhaustive testing is not required
unless targeted suites uncover cross-child regressions.
