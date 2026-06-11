# WebUI SemiAI groups detail audit polish

## Goal

Rebuild only the Groups, GroupDetail, and AuditLogs WebUI pages so they visually match the completed AppShell + Dashboard/Bot/Engine SemiAI baseline and the provided static prototypes, while preserving existing API usage and business behavior.

## What I already know

* User explicitly requested a new/continued Trellis task for the third WebUI SemiAI style round.
* Primary visual reference: `prototype/e60a4820-807f-4559-bf73-9af19845386d.png`.
* Static prototypes: `prototype/groups.html`, `prototype/group-detail.html`, `prototype/audit.html`, and `prototype/assets/styles.css` show compact filters, light panels, status dots/pills, hybrid table rows, object detail headers, and activity/timeline audit rows.
* Existing React pages are `web/src/pages/Groups.tsx`, `web/src/pages/GroupDetail.tsx`, and `web/src/pages/AuditLogs.tsx`.
* Existing shared UI baseline already includes `AppShell`, `panel`, `metric`, `status-pill/status-dot`, `activity`, `table`, button, and compact modal styles in `web/src/styles.css`.
* `StatusBadge` already emits `status-pill` + `status-dot` classes and should be reused for job/validation statuses.
* API contracts in `web/src/api/types.ts` and `web/src/api/client.ts` already support the required data; this task should not modify backend logic or API contracts unless a true type gap is found.

## Assumptions

* No backend/API type changes are required because the requested work is visual/UI layout only.
* Existing route behavior and data loading are authoritative: filters, refresh, pagination/load more, details navigation, save settings, manual summary trigger, job polling, and audit before/after collapse must keep working.
* Screenshot verification can use locally seeded/mockable dev state if the live API does not have production-like data available.

## Requirements

* Limit implementation scope to `Groups`, `GroupDetail`, `AuditLogs`, and necessary shared CSS.
* Do not change backend business logic.
* Do not add UI framework dependencies.
* Continue existing SemiAI baseline instead of redesigning Dashboard/Bot/Engine.
* Groups page:
  * Preserve filters, refresh, load more/pagination, and detail navigation.
  * Make filter area compact and aligned with current tokens.
  * Present groups as a clearer table/card hybrid with readable group identity, chat info, summary switch, interval, profile, and latest summary state.
  * Use `status-pill/status-dot` for status presentation.
  * Keep empty/loading states simple and visually aligned.
* GroupDetail page:
  * Use object detail header with back action, group icon, title, chat type/id, discovered time, refresh, and trigger action.
  * Align summary settings, current status, active job, recent jobs, and result information with panel/table/activity styles.
  * Preserve save settings, trigger summary, poll job, and back-to-list behavior.
  * Keep form density and button treatment consistent with Bot/Engine.
* AuditLogs page:
  * Make filters compact while preserving refresh/search behavior.
  * Present logs as activity/timeline rows with clear actor/action/entity/time hierarchy.
  * Preserve before/after collapse behavior, restyled to match local tokens.
  * Ensure JSON/pre areas are readable and do not break layout.
  * Preserve load more behavior.

## Acceptance Criteria

* [ ] `cd web && npm run typecheck` passes.
* [ ] `cd web && npm run build` passes.
* [ ] No backend files are changed unless API contract changes are necessary and tested.
* [ ] Browser screenshot check covers `/groups`, one valid `/groups/:id` detail page, `/audit-logs`, and one existing non-round page (`/bot` or `/engine`).
* [ ] New styles do not visibly break Dashboard/Bot/Engine baseline.
* [ ] Final response includes modified files, verification commands, screenshot observations, and remaining risks.

## Out of Scope

* Dashboard, Bot, or Engine redesigns.
* Backend behavior or schema changes.
* New UI framework dependencies.
* New product features, new filters, or new data fields not already available from the API.
* Broad CSS/token rewrites unrelated to these three pages.

## Technical Notes

* `web/src/pages/Groups.tsx` currently uses Semi `Card` around filters and table; this should be brought closer to existing custom `panel`/`data-table` styling.
* `web/src/pages/GroupDetail.tsx` already has the required behaviors but needs object-head/panel/activity treatment and better active/recent job presentation.
* `web/src/pages/AuditLogs.tsx` currently uses Semi `Collapse`; preserving collapse can be done through Semi Collapse or local `<details>` only if behavior remains equivalent.
* Existing `web/src/styles.css` contains reusable primitives around line 430+ and page-specific Bot/Engine styles around the object-head/panel/compact-card sections.
