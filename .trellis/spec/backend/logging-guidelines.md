# Logging Guidelines

> How logging is done in this project.

---

## Overview

The backend uses Python's standard `logging` module. Logs are written to the container stdout/stderr stream and must be readable through `docker logs` / `docker compose logs` without requiring Docker's `--timestamps` flag.

---

## Log Levels

<!-- When to use each level: debug, info, warn, error -->

(To be filled by the team)

---

## Structured Logging

### Scenario: Container-readable timestamped logs

#### 1. Scope / Trigger

- Trigger: Backend application startup and Docker Compose operation logs.
- Reason: Operators need event timing from `docker logs` output even when they do not pass `-t` / `--timestamps`.

#### 2. Signatures

- Application logging setup:
  ```python
  logging.basicConfig(
      level=logging.INFO,
      format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
      datefmt="%Y-%m-%dT%H:%M:%S%z",
      force=True,
  )
  ```
- Uvicorn should be configured with `log_config=None` so it does not replace the application logging configuration.
- Alembic's `alembic.ini` formatter should use the same date-first pattern for startup migration logs.

#### 3. Contracts

- Every application log line should include timestamp, level, logger name, and message.
- Startup migration logs should also include a timestamp.
- Secret redaction rules still apply; timestamps must not be added by logging raw config or payload values.

#### 4. Validation & Error Matrix

- Missing logging configuration -> log lines lack timestamps.
- Uvicorn default logging overrides app config -> web server logs may lose the expected format.
- Alembic formatter without `asctime` -> migration logs during container startup lack timestamps.

#### 5. Good/Base/Bad Cases

- Good: `2026-06-11T05:12:30+0000 INFO [summary_relay_bot.main] Starting Summary Relay Bot...`
- Base: Uvicorn startup messages follow the configured timestamped root logging format.
- Bad: `INFO:summary_relay_bot.main:Starting Summary Relay Bot...`

#### 6. Tests Required

- Unit test should assert the configured formatter includes the project log format and date format.
- Compile/test checks should cover import safety after logging setup changes.

#### 7. Wrong vs Correct

##### Wrong

```python
logging.basicConfig(level=logging.INFO)
```

##### Correct

```python
configure_logging()
```

---

## What to Log

<!-- Important events to log -->

(To be filled by the team)

---

## What NOT to Log

<!-- Sensitive data, PII, secrets -->

(To be filled by the team)
