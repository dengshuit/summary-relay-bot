# Rebuild WebUI in SemiAI reference style

## Goal

Rebuild the current React WebUI into a high-density, light, SemiAI-style operations console. The primary visual target is `prototype/e60a4820-807f-4559-bf73-9af19845386d.png`; the existing static prototype pages under `prototype/*.html` are the business-structure reference for summary-relay-bot-specific screens.

The change exists because the current WebUI renders as a functional Semi UI default admin shell, while the desired product should feel like a polished AI SaaS dashboard: clear navigation groups, compact data cards, rich dashboard modules, light shadows, soft status colors, and dense-but-readable tables.

## What I already know

* The primary visual reference is `prototype/e60a4820-807f-4559-bf73-9af19845386d.png`.
* The static prototype already does a strong job translating that reference into this product domain.
* Current React implementation lives under `web/src`.
* Current app routes are Dashboard, Bot, Engine, Groups, GroupDetail, AuditLogs, and Login.
* Current shell uses Semi `Layout`, `Nav`, `Button`, and `Avatar` in `web/src/components/AppShell.tsx`.
* Current Dashboard in `web/src/pages/Dashboard.tsx` only renders a title, restart banner, four metric cards, quick actions, and recent audit logs.
* Current CSS in `web/src/styles.css` has minimal token coverage and leaves many details to Semi defaults.
* Static prototype Dashboard includes welcome header, restart summary, KPI cards, trend chart, donut chart, group ranking, activity stream, and CTA.
* Browser-rendered comparison confirmed the largest current gap is Dashboard: the current first screen has sparse cards and large blank areas, while the reference/prototype has a complete operations dashboard.
* Browser-rendered comparison also confirmed AppShell, Bot, Engine, Groups, GroupDetail, and AuditLogs all show default-admin visual drift.

## Assumptions

* Prefer changing the frontend first; do not change backend business behavior unless required to support existing frontend data display.
* Keep the existing React + Semi UI stack.
* Avoid adding new UI framework dependencies.
* It is acceptable to build custom visual primitives around or alongside Semi components.
* Where backend APIs do not yet expose chart/ranking data, the first implementation may derive conservative display data from existing fields or show stable empty/placeholder states, but the layout should match the target style.

## Requirements

### Visual Direction

* Use the reference image as the primary style guide:
  * light app background;
  * white card surfaces;
  * weak borders and soft shadows;
  * 12-16px rounded cards;
  * compact typography;
  * purple primary actions/selection;
  * green/blue/orange/red soft status accents;
  * high information density without crowding.
* Use `prototype/*.html` as the business layout guide:
  * `prototype/index.html` for Dashboard;
  * `prototype/bot.html` for Bot;
  * `prototype/engine.html` for Engine;
  * `prototype/groups.html` for Groups;
  * `prototype/group-detail.html` for GroupDetail;
  * `prototype/audit.html` for AuditLogs.
* Do not ship a generic Semi default admin look.

### Shared UI System

* Replace or heavily customize the current shell so it matches the reference/prototype:
  * grouped sidebar sections;
  * active nav state;
  * Bot pending badge;
  * collapse behavior;
  * bottom GitHub/project chip;
  * topbar with global refresh and user/session cluster.
* Establish shared UI primitives before page-specific work:
  * app shell;
  * panel/card;
  * metric card;
  * status dot;
  * status pill;
  * activity list;
  * data table;
  * section header / panel header;
  * lightweight button variants.
* Keep styles centralized enough that pages do not diverge.

### Dashboard

Dashboard is the first page to rebuild and is the primary acceptance surface.

* Add a welcome/header block modeled on the prototype/reference.
* Keep restart pending visibility and preserve expand/detail behavior where already available.
* Render four compact KPI cards with icon badges and clear value hierarchy.
* Add a trend chart panel in the reference/prototype style.
* Add a group state donut/distribution panel.
* Add group summary ranking.
* Add recent configuration activity stream with icon/status treatment.
* Add bottom CTA/quick configuration band.
* Avoid large blank card interiors.

### Remaining Pages

After the shell and Dashboard establish the style system:

* Bot page should use an object detail header, restart warning, basic configuration card, validation status card, and Telegram identity card.
* Engine page should use compact Provider/Profile cards with status lights, clear fields, action footers, and dashed add cards.
* Groups page should use a high-density table with status treatment and lightweight row actions.
* GroupDetail page should use an object detail header, summary settings, status overview, recent summary history, and manual trigger state.
* AuditLogs page should use a timeline-style audit stream with warning nodes and before/after diff display.

## Acceptance Criteria

* [ ] The current WebUI no longer reads as a default Semi admin shell at 1440px desktop width.
* [ ] AppShell visually matches the reference/prototype structure: grouped sidebar, topbar, user/session cluster, bottom project/GitHub chip.
* [ ] Dashboard contains all major prototype modules: welcome, restart banner, KPI cards, trend panel, donut panel, ranking, activity stream, CTA.
* [ ] Dashboard has no large unexplained blank card areas in normal loaded state.
* [ ] Shared card/status/table/button styles are reused across pages.
* [ ] Bot, Engine, Groups, GroupDetail, and AuditLogs either match the static prototype or intentionally reuse the new shared primitives.
* [ ] Mobile/narrow widths do not overlap text or controls.
* [ ] `npm run typecheck` passes in `web/`.
* [ ] `npm run build` passes in `web/`.
* [ ] Browser screenshots are captured for `/`, `/bot`, `/engine`, `/groups`, `/groups/1`, and `/audit-logs`.

## Definition of Done

* Requirements above are implemented or explicitly deferred in this PRD.
* Type-check/build pass.
* Relevant browser screenshots are inspected.
* Any backend API changes, if needed, are minimal and covered by tests.
* No unrelated refactors, dependency additions, or formatting churn.

## Out of Scope

* Replacing React, Vite, or Semi UI.
* Adding a new charting dependency unless clearly necessary.
* Changing Telegram bot behavior.
* Changing authentication behavior.
* Reworking backend persistence or scheduler logic.
* Pixel-perfect clone of unrelated SemiAI sample copy/content.

## Technical Notes

* Current route shell: `web/src/app/App.tsx`.
* Current navigation shell: `web/src/components/AppShell.tsx`.
* Current Dashboard: `web/src/pages/Dashboard.tsx`.
* Current global styles: `web/src/styles.css`.
* Current API client/types: `web/src/api/client.ts`, `web/src/api/types.ts`.
* Current static prototype assets: `prototype/assets/styles.css`, `prototype/assets/app.js`.
* Browser comparison screenshots were generated during planning under `/tmp/prototype-*.png` and `/tmp/current-*.png`; these are working-session evidence, not committed artifacts.

## Implementation Plan

1. Build/replace shared visual primitives and AppShell.
2. Rebuild Dashboard first using those primitives.
3. Verify Dashboard against the reference image and `prototype/index.html`.
4. Rebuild Bot and Engine.
5. Rebuild Groups, GroupDetail, and AuditLogs.
6. Run type-check/build and browser screenshot verification.

## Open Question

* Should the first implementation pass cover only AppShell + Dashboard, or should it attempt the full set of pages in one task?
