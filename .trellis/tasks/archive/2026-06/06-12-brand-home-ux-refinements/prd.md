# Brand and home UX refinements

## Goal

Improve the management UI brand polish, dashboard navigation ergonomics, time-aware welcome message, and third-party Telegram command behavior without changing unrelated bot or admin workflows.

## Requirements

- Set the browser document title to a brand-related name instead of the default template title.
- Add a favicon/logo for browser tabs using the existing SummaryBot visual identity.
- For non-owner private users, `/start` and `/help` must be handled directly by the bot with an English prompt telling them they can just send a normal message. These commands must not be relayed to the administrator.
- On the dashboard, the four top metric cards must be clickable and route to their matching pages:
  - Bot service instance -> Bot configuration.
  - Group information -> Groups.
  - LLM channels -> Engine.
  - 24h summary jobs -> Summaries.
- Rename the dashboard card labels:
  - `已拉入群组` -> `群组信息`.
  - `全局摘要引擎` -> `LLM渠道`.
- The dashboard welcome headline must change by local time of day, including an appropriate icon and wording for the current period.
- Remove the visible `ADMIN TOKEN IP AUTH` and `Session token active in browser` copy from the dashboard header.

## Acceptance Criteria

- [x] `web/index.html` uses a SummaryBot-related title and references a tab icon.
- [x] The tab icon asset exists under `web/public/` or another Vite-served static path and uses the existing brand visual direction.
- [x] Non-owner private `/start` and `/help` messages receive a direct English guidance response and are not processed by the private relay handler.
- [x] Admin `/start` and `/help` behavior remains unchanged.
- [x] The four dashboard metric cards navigate to `/bot`, `/groups`, `/engine`, and `/summaries` respectively.
- [x] The group and LLM card labels match the requested Chinese names.
- [x] The welcome headline and icon are computed from the current hour rather than hard-coded to afternoon.
- [x] The dashboard header no longer displays the token/IP/session text.
- [x] Relevant backend unit tests and frontend type/build checks pass, or any inability to run them is documented.

## Notes

- Scope is limited to the requested UI and command-handling changes.
