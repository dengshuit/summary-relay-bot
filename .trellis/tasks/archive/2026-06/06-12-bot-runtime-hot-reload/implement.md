# Bot Runtime Hot Reload Implementation Plan

## Preconditions

- Active-summary policy is resolved: reload-required Bot instance changes must fail immediately with `409 runtime_busy` when any Bot-delivering summary is active.
- Task remains in `planning` until PRD/design/implementation plan are reviewed.
- Before implementation, load `trellis-before-dev` and backend Web API contract guidance.

## Phase 1: Runtime State and Manager Skeleton

- Add a Telegram runtime manager module.
- Define redacted runtime state dataclass.
- Add manager constructor dependencies:
  - bootstrap config or app config factory inputs
  - env mapping
  - shared engine/session factory
  - secret service
- Add manager methods:
  - `start_from_db()`
  - `reload_from_db()`
  - `stop()`
  - `state_snapshot()`
- Add tests for state transitions with fake Bot/Dispatcher/Scheduler.

Validation:

```bash
python3 -m pytest -q tests/unit/test_main.py
```

## Phase 2: Refactor Startup Lifecycle

- Refactor `RuntimeApp` to include the manager instead of static polling resources.
- Refactor `run_runtime_app()` so Web API is the long-lived task and polling task completion does not stop Web API.
- Split polling resource cleanup so shared engine is not disposed by polling cleanup.
- Store the manager in FastAPI `app.state`.
- Change dashboard dependency to read dynamic manager state instead of static `telegram_startup`.
- Preserve existing behavior when no enabled Bot exists: WebUI starts and polling does not.

Validation:

```bash
python3 -m pytest -q tests/unit/test_main.py tests/integration/test_web_dashboard.py
```

## Phase 3: Summary Reload Gate

- Add `SummaryReloadGate`.
- Pass the gate through dispatcher dependency injection and scheduler kwargs.
- Update Bot-delivering summary paths:
  - Telegram `/summary`
  - scheduled summaries
- Ensure gate tracks active Bot-delivering summary execution without changing existing summary job finalization semantics.
- Leave Web manual summary jobs unblocked by Bot runtime reload unless existing active-job constraints apply.
- Add tests for:
  - active Bot-delivering summary increments/decrements count
  - active summary conflict is visible to reload coordinator
  - exceptions inside summary execution still decrement active count

Validation:

```bash
python3 -m pytest -q tests/unit/test_summary_jobs.py tests/unit/test_scheduler.py tests/unit/test_web_summary_jobs_api.py
```

## Phase 4: Bot API Reload Integration

- Add route-level helper to detect reload-required create/patch payloads.
- For name-only or validation-only changes, keep existing behavior.
- For reload-required create/patch:
  - call manager-coordinated change method
  - reject immediately with `409 runtime_busy` if a Bot-delivering summary is active
  - stop old polling only after active-summary check passes
  - apply DB change
  - rebuild/start runtime from DB
  - clear restart flags only after success
- Add safe `409 runtime_busy` error response before commit when active summary blocks reload.
- Add safe reload failure handling:
  - config can remain saved only after active-summary check passes and old runtime stop begins
  - `needs_restart` stays true when new runtime fails
  - dashboard state shows safe failure detail
- Consider adding `POST /api/bot/reload` for explicit retry.

Validation:

```bash
python3 -m pytest -q tests/unit/test_web_bot_api.py tests/unit/test_web_auth.py
```

## Phase 5: Restart Flag and Runtime Convergence Helpers

- Add service helper to clear relevant Bot restart flags after runtime convergence.
- Define convergence cases:
  - running enabled Bot ID matches DB enabled Bot and resources started successfully
  - no enabled Bot in DB and manager state is `no_enabled_bot`
- Ensure failed reload does not clear flags.
- Ensure affected old disabled Bot instance from a switch is cleared only after successful switch.

Validation:

```bash
python3 -m pytest -q tests/unit/test_runtime_config.py tests/unit/test_web_bot_api.py tests/integration/test_web_dashboard.py
```

## Phase 6: Documentation and API Types

- Update README/README.zh-CN:
  - Bot token/owner/enabled changes hot reload when no active summary blocks reload
  - active summaries can produce `runtime_busy`
  - env/bootstrap variables still require restart
- Update Web API schemas/types only if backend response contracts change.
- Keep secret-redaction language intact.

Validation:

```bash
python3 -m compileall -q src tests migrations
```

## Final Quality Gate

Run targeted tests:

```bash
python3 -m pytest -q \
  tests/unit/test_config.py \
  tests/unit/test_runtime_config.py \
  tests/unit/test_main.py \
  tests/unit/test_scheduler.py \
  tests/unit/test_summary_jobs.py \
  tests/unit/test_web_bot_api.py \
  tests/unit/test_web_summary_jobs_api.py \
  tests/integration/test_web_dashboard.py \
  tests/integration/test_persistence.py
```

Run compile check:

```bash
python3 -m compileall -q src tests migrations
```

If project dependencies are unavailable in the current shell, report the exact missing dependency and the substitute checks run.

## Risky Files

- `src/summary_relay_bot/main.py`: process lifecycle, engine disposal, Web/polling task ownership.
- `src/summary_relay_bot/web/routes/bot.py`: route semantics, secret safety, reload error handling.
- `src/summary_relay_bot/services/runtime_config.py`: restart flag behavior and audit safety.
- `src/summary_relay_bot/scheduler.py`: job ownership and shutdown semantics.
- `src/summary_relay_bot/services/summary_jobs.py`: active summary gate and job finalization.
- `src/summary_relay_bot/web/routes/dashboard.py`: dynamic runtime state exposure.
- `tests/unit/test_main.py`: existing lifecycle assumptions will need careful updates.

## Rollback Points

- After Phase 2, manager can be start-only with no API-triggered reload.
- After Phase 3, gate can be disabled from routes while summary tests remain useful.
- After Phase 4, automatic reload can be guarded behind a small internal helper and reverted to current `needs_restart` behavior if instability appears.
