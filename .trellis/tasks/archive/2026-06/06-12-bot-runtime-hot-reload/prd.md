# Bot runtime hot reload

## Goal

Support reliable hot reload for Bot runtime configuration in the server process, so WebUI changes to the active Bot instance can take effect without restarting the whole service.

The target runtime is still a single-process application: FastAPI WebUI/API remains available while Telegram polling can be started, stopped, rebuilt, or left failed independently.

## User Value

- Changing Bot token, owner ID, or enabled Bot instance should not require container/process restart in normal operation.
- An empty database or "no enabled bot" state can be configured through the WebUI, then start polling in the already-running service.
- Reload behavior must be conservative around summaries: no summary should be lost, stuck as `running`, or delivered to the wrong owner after a reload-required config change.

## Confirmed Facts

- `build_runtime_app()` loads the enabled Bot only once during startup and creates polling resources only if a Bot is available.
- The current `run_runtime_app()` runs Web API and polling as sibling tasks and cancels the whole runtime when either completes.
- `update_bot_instance()` marks `needs_restart=True` for `owner_id`, non-empty `bot_token`, and enabled-state changes, but no current code consumes that flag to reload polling.
- Dashboard exposes restart pending state by querying `BotInstance.needs_restart`.
- LLM Provider, Summary Profile, and Summary Profile runtime config are loaded from the database when a summary runs, so they are not part of Bot runtime hot reload.
- `SummaryJob` has `pending`, `running`, `succeeded`, `failed`, and `blocked` statuses. A partial unique index allows only one active `pending` or `running` job per group.
- Existing summary jobs use leases and `finish_summary_job()` clears `lease_expires_at`; cancelled or interrupted jobs must be finished explicitly or they can block later summaries until lease handling runs.

## Requirements

1. Introduce a Telegram runtime manager that owns polling lifecycle independently from the Web API server.
2. The Web API must remain available when Telegram polling is stopped, missing configuration, failed, or reloading.
3. Reload-required Bot changes must be applied without a process restart:
   - replacing Bot token with a non-empty value
   - changing owner ID
   - enabling a Bot instance
   - disabling the currently running Bot instance
   - switching from one enabled Bot instance to another
   - configuring an enabled Bot after the service started with no enabled Bot
4. Non-runtime Bot changes must not trigger reload:
   - Bot display name
   - validation status / Telegram identity fields
   - blank, whitespace-only, null, or missing `bot_token` in PATCH
5. Runtime reloads must be serialized. Concurrent reload requests must not create overlapping polling tasks or multiple active aiogram `Bot` sessions.
6. Runtime reload must rebuild the full Bot-bound resource set:
   - aiogram `Bot`
   - `Dispatcher`
   - registered routers / owner filters
   - command menu setup
   - `BotScheduler` and scheduled summary jobs
7. A successful reload must clear relevant `needs_restart` flags. A failed reload must leave `needs_restart=True` and expose a redacted failure detail through dashboard/runtime state.
8. If no Bot instance is enabled after a change, reload must stop polling and leave WebUI/API running.
9. If the enabled Bot token cannot be decrypted or used to construct polling resources, reload must fail safely without leaking secrets.
10. Summary handling during reload:
    - if any Bot-delivering summary is active, reload-required Bot config updates must fail immediately with a safe conflict response
    - the conflicting config update must not be committed
    - old runtime should continue unchanged after the conflict response
    - no summary job may be left permanently `running` because of reload
    - summary cursor must not be affected by a rejected reload attempt
11. Web manual summary jobs that do not deliver through Telegram are not blocked by Bot owner/token reload unless they share the same group active-job constraint.
12. API responses, logs, audit records, and runtime state must not expose Bot tokens, encrypted token material, raw owner IDs, `WEBUI_ADMIN_TOKEN`, or `SETTINGS_ENCRYPTION_KEY`.
13. The implementation must preserve existing `/api/bot` request/response contracts except for documented safe error responses on runtime-busy reload-required changes.

## Acceptance Criteria

- [ ] Starting the service with no enabled Bot starts WebUI/API only; creating or enabling a valid Bot through the API starts polling without process restart.
- [ ] Changing owner ID rebuilds dispatcher filters, scheduler kwargs, and command menus so later admin commands and summary delivery use the new owner.
- [ ] Replacing Bot token closes the old Bot session and starts polling with the new token, without overlapping polling tasks.
- [ ] Disabling the current Bot stops polling and keeps WebUI/API healthy.
- [ ] Switching enabled Bot instances stops the old polling runtime and starts the newly enabled Bot runtime.
- [ ] Successful reload clears `needs_restart` for affected Bot instances and removes dashboard `restart_pending` entries.
- [ ] Failed reload keeps `needs_restart=True`, records safe runtime failure state, and does not leak secrets.
- [ ] If a reload-required config change is requested while a Bot-delivering summary is active, the API immediately returns a safe `409` conflict and does not commit the Bot config change.
- [ ] No test leaves a `SummaryJob` in `running` because reload interrupted execution.
- [ ] Existing Bot API secret-redaction tests continue to pass.
- [ ] New unit tests cover manager start/stop/reload, no-enabled-bot startup, reload failure, and active-summary conflict.
- [ ] New route tests cover create-enabled hot start, PATCH token hot reload, PATCH owner hot reload, enable/switch hot reload, and busy summary conflict.
- [ ] `python3 -m compileall -q src tests migrations` passes.
- [ ] Relevant pytest targets pass in an environment with project test dependencies installed.

## Out Of Scope

- Multi-process coordination or distributed locks.
- Restarting the Python process or container from inside the app.
- Redis, queues, or a separate Telegram worker service.
- Webhook support.
- Multi-admin authorization redesign.
- Frontend visual redesign. Minimal frontend/API type alignment may be included only if backend response contracts change.
- Hot reload for environment/bootstrap variables such as `DATABASE_URL`, `SETTINGS_ENCRYPTION_KEY`, `WEBUI_ADMIN_TOKEN`, `WEBUI_HOST`, or scheduler process-level env options.

## Resolved Decisions

- If a Bot-delivering summary is active, WebUI/API attempts to modify reload-required Bot instance fields must immediately fail with `409 runtime_busy`. The config update is not saved, and the old runtime continues unchanged.

## Notes

- Keep `prd.md` focused on requirements, constraints, and acceptance criteria.
- Lightweight tasks can remain PRD-only.
- For complex tasks, add `design.md` for technical design and `implement.md` for execution planning before `task.py start`.
