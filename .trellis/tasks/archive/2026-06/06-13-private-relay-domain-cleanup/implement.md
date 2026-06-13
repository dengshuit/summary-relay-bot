# Private relay domain cleanup - Implementation Plan

## Preconditions

- `06-13-telethon-schema-domain-reset` is completed or at least leaves relay-domain schema available.
- Do not start Telethon work in this child.

## Checklist

1. Review current command and handler wiring.
   - `src/summary_relay_bot/telegram/commands.py`
   - `src/summary_relay_bot/handlers/admin.py`
   - `src/summary_relay_bot/handlers/admin_groups.py`
   - `src/summary_relay_bot/handlers/group.py`
   - `src/summary_relay_bot/handlers/__init__.py`
   - `src/summary_relay_bot/main.py`

2. Remove group summary command ownership from relay runtime.
   - Update owner command menu to omit `/groups`, `/summary`, `/enable_group`, `/disable_group`, `/set_interval`.
   - Keep `/start`, `/help`, and `/reply` for owner.
   - Keep non-owner `/start` and `/help`.
   - Update owner `/help` text so it does not mention removed group summary commands.
   - Add non-owner unsupported-command handling so removed slash commands are not forwarded to the owner as ordinary private relay messages.
   - Stop registering summary-management handlers on the private relay dispatcher.
   - Stop registering Bot API group collection handlers if they only exist for old group summary collection.

3. Preserve private relay functionality.
   - Ensure ordinary private message relay still persists relay-domain user/message rows and forwards to owner.
   - Ensure reply-map replies and `/reply` still route through relay-domain repositories.
   - Ensure runtime config and startup do not query or require `summary_userbots`.

4. Adjust tests.
   - Update command/menu tests for new owner/non-owner command boundary.
   - Add `tests/unit/test_admin_commands.py` if no focused command test file exists.
   - Add or update router registration tests proving summary group handlers are not included.
   - Add assertions that `admin.build_router()` no longer registers `/summary` and owner help text excludes removed commands.
   - Update or remove handler-layer `/summary` tests in `tests/unit/test_summary_jobs.py`; service-level summary job tests may remain for later WebUI/manual trigger work.
   - Keep private relay and admin reply regression tests passing.
   - Add success-path coverage for mapped owner replies, `/reply <user_id> <message>`, and unknown user rejection if not already covered.
   - Keep runtime startup tests proving no enabled bot skips polling and enabled relay bot can build without userbot.

5. Documentation touch only if needed.
   - Full command/userbot docs are owned by final integration child.
   - Update README/README.zh-CN command sections enough that they no longer state removed group summary Telegram commands as supported.
   - Leave detailed WebUI/userbot operational docs to the final integration child.

6. Preserve schema reset compatibility aliases.
   - Do not remove `BotInstance`, `PrivateUser`, `PrivateMessage`, `AdminReplyMap`, `DeliveryAttempt`, `GroupChat`, or `GroupSummarySettings` aliases from `db.models` in this child.
   - Use relay-domain names only in files touched for private relay behavior when the change is local and low-risk.

## Validation Commands

```bash
python3 -m compileall -q src tests migrations
python3 -m pytest tests/unit/test_authorization.py -q
python3 -m pytest tests/unit/test_admin_commands.py -q
python3 -m pytest tests/unit/test_private_relay.py tests/unit/test_admin_replies.py -q
python3 -m pytest tests/unit/test_summary_jobs.py -q
python3 -m pytest tests/unit/test_main.py -q
python3 -m pytest tests/unit/test_web_bot_api.py -q
```

If command-specific tests live in another file, run that file as well.

## Risk Areas

- Removing handlers from registration is safer than deleting modules now, because later summary children may still need to reference old code while moving functionality to WebUI.
- Non-owner command handling depends on router order; keep admin/non-owner command router before private-user catch-all.
- The scheduler still has summary job concepts before the summary persistence child. Avoid broad scheduler refactor here unless command removal requires it.

## Completion Criteria

- Relay command menus and handlers no longer expose Telegram group summary management.
- Private relay message forwarding and reply mapping tests pass.
- Relay runtime does not depend on Telethon/userbot configuration.
- Validation commands pass.
