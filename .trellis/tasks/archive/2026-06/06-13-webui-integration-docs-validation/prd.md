# WebUI integration docs and validation

## Goal

Finish the integrated WebUI experience, documentation, and cross-child validation for the refactored private relay and Telethon group summary architecture.

Parent task: `06-13-telethon-group-summary-refactor`.

## Requirements

- WebUI must clearly separate private relay configuration from summary userbot configuration.
- WebUI must support userbot authorization status, group discovery refresh, explicit group enablement, summary settings, manual summary trigger, summary job/result inspection, and delivery attempt status.
- WebUI should retain existing LLM Provider and Summary Profile management.
- Documentation must explain fresh database reset expectations and that old development data is not preserved.
- Documentation must explain Telethon setup, userbot risks, session secrecy, proxy requirements, and first-version limitations.
- Final validation must verify private relay still works without userbot configuration and group summary can work without relay notification success.

## Acceptance Criteria

- [ ] WebUI navigation and pages expose distinct private relay and group summary concepts.
- [ ] Userbot configuration/auth, group discovery, enablement, manual summary, scheduled summary, summary results, and delivery status are usable from WebUI.
- [ ] Existing LLM Provider and Summary Profile UI/API remain usable.
- [ ] README/operations docs cover Telethon credentials, WebUI auth flow, session secret risks, proxy dependency, schema reset, and no active historical backfill.
- [ ] Cross-child integration tests or smoke tests cover private relay without userbot, userbot summary without relay bot, and summary notification when relay bot is available.
- [ ] Final quality gate runs relevant backend tests, frontend checks/build, and documentation review.

## Notes

- This child should run after the implementation-focused children so it can validate the integrated workflow.
