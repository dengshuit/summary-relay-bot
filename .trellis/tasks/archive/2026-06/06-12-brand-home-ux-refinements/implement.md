# Implementation Plan

1. Update static brand metadata:
   - Add SummaryBot favicon SVG under `web/public/`.
   - Update `web/index.html` title and icon links.
2. Update Telegram non-owner command handling:
   - Register non-owner private `/start` and `/help` to direct guidance.
   - Ensure the guidance handler does not relay those commands.
   - Add focused unit tests for non-owner `/start` and `/help`.
3. Update dashboard UX:
   - Add time-of-day welcome helper and use it in the header.
   - Remove token/IP/session text block.
   - Make the four metric cards clickable buttons.
   - Rename requested card labels.
4. Validate:
   - Run focused backend tests for command handling/private relay behavior.
   - Run frontend type check/build from `web/`.
   - Run any existing smoke tests relevant to static frontend serving if needed.

## Rollback Points

- Revert `web/index.html` and favicon asset if static metadata causes packaging issues.
- Revert `Dashboard.tsx` card wrappers if layout or accessibility regressions appear.
- Revert `admin.py` registrations if command routing conflicts with owner command behavior.
