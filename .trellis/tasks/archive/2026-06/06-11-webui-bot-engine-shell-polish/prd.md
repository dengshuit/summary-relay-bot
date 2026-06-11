# Fix WebUI Bot, Engine, and Shell polish

## Goal

Fix the UI issues found after the second SemiAI-style rebuild pass: make the Bot empty state accurately reflect current backend capabilities, finish the Engine tab/modal visual polish, and simplify the AppShell top-right session area for token-based authentication.

## Requirements

* Bot page empty state must allow the administrator to create the first Bot instance through Web UI.
* Add only the minimum missing Web API wrapper needed for Bot creation, reusing existing service-layer `create_bot_instance` rules.
* Engine page must use the current AppShell/panel/button/status visual language for page actions, tabs, add cards, Provider/Profile cards, and create/edit modals.
* AppShell top-right area must remove refresh, notification, and help auxiliary buttons.
* AppShell must show a default token-session username/avatar without a dropdown affordance; logout remains available as a direct action.
* Do not change backend business rules or add UI framework dependencies.
* Do not redesign Groups, GroupDetail, or AuditLogs beyond avoiding shared-style regressions.

## Acceptance Criteria

* [ ] `/bot` empty state offers a WebUI creation path when no Bot instances exist.
* [ ] Creating the first Bot through WebUI stores encrypted token material and never returns plaintext token/owner id.
* [ ] `/engine` Provider tab refresh and add/edit modal no longer read as old/default Semi styling.
* [ ] `/engine` Summary Profile tab uses the same compact card, status pill, add card, modal, and button styling.
* [ ] AppShell topbar only includes nav toggle, page meta, token session identity, and logout.
* [ ] `/groups` or `/` remains visually intact after shared style changes.
* [ ] `cd web && npm run typecheck` passes.
* [ ] `cd web && npm run build` passes.
* [ ] Dev server runs and browser screenshot checks cover `/bot`, `/engine`, and one unaffected page.

## Definition of Done

* Minimal scoped React/CSS edits only.
* Existing API contracts and page behaviors preserved.
* Validation commands and screenshot checks recorded in final response.

## Technical Approach

Use the existing round-two primitives (`object-head`, `panel`, `compact-card`, `status-pill`, `add-card-button`, shared Semi button overrides) and add targeted classes where Semi defaults are still bleeding through. Add the missing Bot creation Web endpoint/client/modal by delegating to `create_bot_instance`, then reload into the existing Bot edit/validate flow. Simplify AppShell markup rather than creating unused dropdown state.

## Out of Scope

* New backend Bot business rules beyond exposing the existing creation service via Web API.
* Authentication/user profile management.
* New UI dependencies or a broader redesign of unrelated pages.
* Reworking Groups, GroupDetail, AuditLogs, or Dashboard.

## Technical Notes

* `web/src/api/client.ts` currently exposes `api.bot.list`, `api.bot.update`, and `api.bot.validate`; no Bot create method is available.
* README and `.env.example` state Bot token/owner ID are managed through WebUI, so the missing creation path is a product/API gap rather than just an empty-state wording issue.
* `web/src/api/types.ts` models `BotListResponse` as `active` plus `items`; empty list is valid and currently handled as an Empty state.
* `web/src/components/AppShell.tsx` currently renders topbar refresh, notification, help, session caret, and logout.
* `web/src/pages/Engine.tsx` already has compact-card structure, but page actions and modals still rely heavily on default Semi styling.
