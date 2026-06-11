# WebUI SemiAI Bot and Engine Style Rebuild

## Goal

Continue the second pass of the WebUI SemiAI-style rebuild. Starting from the already completed AppShell and Dashboard visual baseline, rebuild only the Bot page and Engine page so they align more closely with the SemiAI reference image and the existing static prototypes.

## Requirements

* Use `prototype/e60a4820-807f-4559-bf73-9af19845386d.png` as the primary visual reference.
* Use `prototype/bot.html`, `prototype/engine.html`, and `prototype/assets/styles.css` as the page-structure and component-density references.
* Only change Bot, Engine, and necessary shared frontend styles/components.
* Do not change backend business logic or API behavior.
* Do not add a new UI framework dependency.
* Continue reusing the previous AppShell/Dashboard visual primitives: panel, metric, status, activity, table, and button styling.
* Do not rebuild Groups, GroupDetail, or AuditLogs; only ensure new shared styles do not visually break them.

## Bot Page

* Replace the generic page header with an object detail header containing Bot icon, selected Bot name, status, refresh action, and test action.
* Preserve Bot instance selection and the existing save/test behavior.
* Preserve the restart warning and render it with the existing soft warning visual language.
* Make the basic configuration card, runtime status card, and Telegram identity/secret status card closer to the prototype layout.
* Keep `SecretInput` security semantics: no plaintext display, new input replaces the secret, empty input means no change.
* Preserve the confirm flow when enabling a different Bot instance.

## Engine Page

* Render Provider and Profile lists as compact cards with status dot/pill, field summary, and action footer.
* Keep existing tabs and behavior, but align their visuals with the new token system.
* Improve create/edit modals for density and consistency with the compact card style without adding new capabilities.
* Render default Profile, secret configured state, enabled state, and validation state with unified `status-pill` / `status-dot` treatment.
* Keep dashed add cards and align them with the prototype style.

## Acceptance Criteria

* [ ] `/bot` uses an object detail header and prototype-like two-column configuration/status layout.
* [ ] `/bot` save, test connection, Bot selection, and secret replacement behavior are unchanged.
* [ ] `/engine` Provider and Profile tabs use compact cards with status summaries and footer actions.
* [ ] `/engine` create/edit modals remain functionally equivalent and visually denser.
* [ ] Shared status and card styles are reused rather than introducing a separate visual system.
* [ ] Groups or Dashboard page is not visually broken by shared style changes.
* [ ] `cd web && npm run typecheck` passes.
* [ ] `cd web && npm run build` passes.
* [ ] Browser screenshot inspection is completed for `/bot`, `/engine`, and `/` or `/groups`.

## Definition of Done

* The requested pages are implemented within the stated scope.
* Type-check and build pass.
* A local dev server is started.
* Browser screenshots are inspected for the required routes.
* Any remaining risks are documented in the final response.

## Out of Scope

* Backend business logic changes.
* New UI framework dependencies.
* Reworking Dashboard, Groups, GroupDetail, AuditLogs, Login, or AppShell behavior.
* New Engine or Bot capabilities beyond existing API actions.
* Pixel-perfect cloning of the SemiAI reference.

## Technical Notes

* Current Bot implementation: `web/src/pages/Bot.tsx`.
* Current Engine implementation: `web/src/pages/Engine.tsx`.
* Shared secret/status/confirm components: `web/src/components/SecretInput.tsx`, `web/src/components/StatusBadge.tsx`, `web/src/components/ConfirmAction.tsx`.
* Shared style baseline: `web/src/styles.css`.
* API fields needed for this task already exist in `web/src/api/types.ts` and `web/src/api/client.ts`.
* Previous baseline task: `.trellis/tasks/archive/2026-06/06-11-webui-semi-ai-style-rebuild/prd.md`.
