# Design

## Boundaries

- Frontend changes stay inside the Vite React app under `web/`.
- Telegram command behavior changes stay in `src/summary_relay_bot/handlers/admin.py`, where owner and non-owner command handlers are registered today.
- No database, API schema, dependency, or routing architecture changes are required.

## Frontend

- `web/index.html` owns the static document title and Vite-served favicon links.
- The tab logo will reuse the existing SummaryBot sidebar SVG shape as a standalone static SVG in `web/public/`.
- `Dashboard.tsx` already receives `setTab` from `App.tsx`; the top metric cards can call existing tab ids to navigate without adding router dependencies to the view.
- Clickable dashboard cards will be rendered as `<button type="button">` elements to preserve keyboard access.
- The welcome message will be computed in `Dashboard.tsx` from `new Date().getHours()` during render. Time buckets:
  - 05:00-11:59: morning.
  - 12:00-17:59: afternoon.
  - 18:00-21:59: evening.
  - 22:00-04:59: night.

## Telegram Commands

- Non-owner private `/help` currently maps to `handle_user_help`; non-owner private `/start` falls through to the private relay router and can be forwarded.
- Register non-owner private `/start` and `/help` to the direct guidance handler before the catch-all private relay router can process the message.
- Reuse one English message for both commands so behavior is predictable and easy to test.
- Owner command registrations remain first-class and unchanged.

## Compatibility

- Browser title/favicon changes are static assets only.
- Existing URLs remain unchanged.
- The requested dashboard card labels are display-only.
