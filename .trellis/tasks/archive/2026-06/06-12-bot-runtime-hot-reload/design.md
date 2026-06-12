# Bot Runtime Hot Reload Design

## Summary

Replace the current "Web API task + polling task race" lifecycle with a long-lived Web API plus an in-process Telegram runtime manager. The manager owns Telegram polling resources and can rebuild them after Bot runtime configuration changes.

The main reliability rule is conservative reload: reload-required Bot config changes must not be committed while an old Bot-delivering summary is still active. If a Bot-delivering summary is active, the API rejects the config update immediately with a safe conflict response and keeps the old runtime unchanged.

## Current Shape

Current startup:

1. `BootstrapConfig.from_env()` reads bootstrap env.
2. `build_runtime_app()` creates engine/session factory and reads enabled Bot once.
3. If no enabled Bot exists, only Web API is created.
4. If a Bot exists, `build_app()` creates Bot, Dispatcher, Scheduler, and handlers.
5. `run_runtime_app()` runs Web API and polling as sibling tasks with `FIRST_COMPLETED`.

Problems for hot reload:

- Stopping polling looks like whole-app termination.
- Web app only stores a static `telegram_startup` snapshot.
- Runtime-bound dependencies are created once and not replaceable.
- Summary jobs can keep running while Bot config changes.

## Proposed Components

### TelegramRuntimeManager

New service-level component, likely in `src/summary_relay_bot/services/telegram_runtime.py` or `src/summary_relay_bot/telegram/runtime.py`.

Responsibilities:

- own the current polling resources
- serialize start/stop/reload with `asyncio.Lock`
- expose a redacted runtime state snapshot for dashboard/API
- build resources from the current enabled Bot DB row
- start and stop polling without stopping Web API
- detect active Bot-delivering summaries before reload-required config changes
- clear `needs_restart` only after successful runtime convergence

State fields:

- `status`: `no_enabled_bot`, `starting`, `running`, `reloading`, `stopped`, `failed`
- `detail`: safe human-readable detail
- `bot_instance_id`: optional active Bot instance ID
- `bot_name`: optional safe Bot display name
- `owner_id_redacted`: optional redacted owner ID if exposed
- `last_reload_at`: optional timestamp
- `last_reload_error`: optional safe error type/message

Do not expose token, encrypted token, raw owner ID, admin token, or encryption key.

### Polling Runtime Resources

Refactor the existing `AppResources` concept into manager-owned polling resources:

- `AppConfig`
- `BotRuntimeConfig`
- owner ID
- aiogram `Bot`
- `Dispatcher`
- `BotScheduler`
- session factory
- secret service
- summary reload gate

Important change: polling resource cleanup must close scheduler and Bot session but must not dispose the shared engine. Engine disposal stays at top-level process shutdown.

### SummaryReloadGate

Add a small concurrency gate passed into Bot-bound summary paths.

Responsibilities:

- count active Bot-delivering summary runs
- report whether a reload-required Bot config change is currently blocked

Suggested API:

```python
class SummaryReloadGate:
    async def enter_bot_delivery_summary(self) -> AsyncContextManager[None]: ...
    async def has_active_bot_delivery_summary(self) -> bool: ...
```

The gate wraps Bot-delivering summary execution and decrements its active count even if the summary fails. A reload-required Bot config change checks the active count before saving any config. If the count is nonzero, the API returns `409 runtime_busy` and does not touch the database.

### Runtime-Bound Summary Paths

Bot-delivering summary paths:

- Telegram `/summary` via `run_manual_summary()` and `run_summary_for_group()`
- scheduled summary via `run_scheduled_summary()` and `run_summary_for_group()`

Non Bot-delivering path:

- Web manual summary job via `run_web_manual_summary_job()` writes DB result only and does not send through Telegram. It does not need to block on Bot reload, beyond existing per-group active-job constraints.

## Reload Data Flow

### Startup

1. Build shared engine/session factory/secret service.
2. Build Web app with manager in `app.state`.
3. In `run_runtime_app()`, call `manager.start_from_db()`.
4. Start Web API and await it.
5. On Web API shutdown, stop manager and dispose engine.

Polling task errors should be captured inside the manager and reflected in runtime state. They should not terminate Web API.

### Create Enabled Bot From No Runtime

1. Web route validates and creates enabled Bot.
2. Route verifies no Bot-delivering summary is active and calls `manager.reload_from_db()`.
3. Manager loads enabled Bot, builds resources, and starts polling.
4. If successful, clear `needs_restart`.
5. If failed, keep WebUI/API running and leave restart pending.

No active Bot-delivering summaries can exist if no polling runtime existed.

### Reload-Required PATCH / Switch / Disable

Use a manager-coordinated transaction for reload-required changes.

1. Route determines that payload can affect runtime:
   - non-empty `bot_token`
   - non-null `owner_id`
   - non-null `enabled`
2. Acquire manager reload lock.
3. Check whether any Bot-delivering summary is active.
4. If active summary exists:
   - do not commit config change
   - do not stop polling
   - return `409 runtime_busy` with safe message
5. Stop scheduler and old polling task, then close old Bot session.
6. Apply DB config change.
7. Build new resources from the now-current enabled Bot.
8. Start new polling if an enabled Bot exists.
9. Clear restart flags on success.
10. If DB update fails validation, rebuild/resume old runtime from unchanged DB and return the validation error.
11. If new runtime build/start fails after DB update, leave WebUI/API running, keep `needs_restart=True`, and expose failure state.

This order prevents old Bot-delivering summaries from using stale owner/token after the config change is committed.

### Name-Only Bot Updates

Name-only updates stay in the existing service path:

- update DB
- write audit
- no manager reload
- no drain
- response returns `needs_restart=False` unless previously pending for another reason

### Validate Bot

Validation continues to use temporary Bot instances and does not affect running runtime unless the user also saves the token later.

## In-Flight Summary Policy

Confirmed policy:

- If a Bot-delivering summary is already running, reload-required Bot config changes are rejected immediately with `409 runtime_busy`.
- The attempted config update is not committed.
- Old polling and scheduler continue unchanged.
- The user can retry after the active summary finishes.
- The system does not force-cancel active summaries in the MVP.

Rationale:

- This preserves existing cursor correctness.
- It avoids leaving `running` jobs behind.
- It avoids delivering summaries to the old owner after the config has changed.
- It avoids making an admin wait on a long LLM/Telegram call inside a config-save request.
- It avoids implementing cancellation recovery for every LLM/Telegram edge case in the first hot-reload change.

Future enhancement:

- Add explicit `cancelled` summary status or reload-abort support if forced reload becomes a product requirement.

## API Contracts

Existing `/api/bot` success schemas remain unchanged.

New or changed errors:

- Reload-required `POST /api/bot` or `PATCH /api/bot` can return:

```json
{
  "error": {
    "code": "runtime_busy",
    "message": "Bot runtime reload is blocked by an active summary; retry after it finishes"
  }
}
```

No raw IDs or secrets in details.

Optional retry endpoint:

- Add `POST /api/bot/reload` for an explicit reload retry after transient failure.
- Response can reuse dashboard runtime state or return a compact safe reload result.
- This endpoint is useful but can be implemented after automatic reload if scope needs to shrink.

Dashboard:

- Replace static `telegram_startup` snapshot with manager state while preserving `status` and `detail` fields.
- Keep `restart_pending` list from `needs_restart`.

## Database Changes

No migration is required for the MVP if the existing `needs_restart` and `SummaryJob` fields are reused.

Service changes:

- add helper to clear Bot restart flags after successful reload
- possibly add helper to update Bot config inside a manager-coordinated callback
- do not store plaintext secrets in any runtime state or audit record

## Failure Modes

### Reload Build Fails

Examples: invalid token format, decrypt failure, Telegram preflight failure.

Behavior:

- WebUI/API remains running.
- Runtime state becomes `failed`.
- `needs_restart` remains true.
- Old runtime may already be stopped if the DB update was committed and new runtime failed. This is acceptable because running old runtime after committing a new token/owner would violate consistency.

### Polling Task Exits Unexpectedly

Behavior:

- Manager marks runtime `failed`.
- WebUI/API remains running.
- `needs_restart` may stay unchanged unless the failure is known to be config-related.
- Dashboard exposes safe detail.

### Active Summary Conflict

Behavior:

- DB config change is not committed.
- Old runtime continues unchanged.
- API returns `409 runtime_busy`.
- No `needs_restart` change caused by this attempted update.

### No Enabled Bot

Behavior:

- Manager stops any current runtime.
- State becomes `no_enabled_bot`.
- WebUI/API remains available.
- Restart flags can be cleared if runtime has converged to "no polling expected".

## Test Strategy

Unit-level:

- manager starts with no enabled Bot
- manager starts with valid enabled Bot
- manager stops current runtime without disposing shared engine
- reload serializes concurrent calls
- reload clears restart flags only on success
- reload failure keeps restart pending
- active summary conflict returns busy and leaves old runtime active
- summary gate tracks active Bot-delivering summaries accurately

Route-level:

- create enabled Bot from no polling starts runtime
- PATCH token triggers reload and closes old session
- PATCH owner rebuilds owner-dependent resources
- PATCH enabled switches active Bot
- PATCH disable current Bot stops polling
- name-only PATCH does not reload
- active summary conflict returns safe `409 runtime_busy`
- secret redaction tests still pass

Integration/smoke:

- compile all Python
- targeted pytest for main/runtime/config/web bot API/scheduler/summary jobs

## Rollback Plan

- Keep existing `needs_restart` semantics until reload success path is verified.
- If runtime manager causes instability, disable automatic reload trigger and fall back to current restart-required behavior by leaving manager start-only.
- The DB schema does not need rollback for MVP.
