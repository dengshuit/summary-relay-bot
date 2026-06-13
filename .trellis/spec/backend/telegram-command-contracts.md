# Telegram Command Contracts

## Scenario: Owner and Non-Owner Private Commands

### 1. Scope / Trigger

- Trigger: adding or changing Telegram bot command handlers under `src/summary_relay_bot/handlers/`.
- Applies to admin commands in `admin.py`, private-user relay routing in `private_user.py`, and router inclusion order in `handlers/__init__.py`.

### 2. Signatures

- Owner private `/start`
- Owner private `/help`
- Non-owner private `/start`
- Non-owner private `/help`
- Non-owner private ordinary messages

### 3. Contracts

- Owner `/start` and `/help` are admin-only private-chat commands.
- Non-owner private `/start` and `/help` must be handled directly by the bot with user guidance text.
- Non-owner private `/start` and `/help` must not be persisted as private relay messages and must not be forwarded to the owner.
- Non-owner private ordinary messages continue through the private relay handler.
- The admin router must be included before the private-user catch-all router so command-specific non-owner handlers can consume `/start` and `/help`.

### 4. Validation & Error Matrix

- Owner private `/start` -> bot status response.
- Owner private `/help` -> admin help response.
- Non-owner private `/start` or `/help` -> direct guidance response.
- Non-owner private admin-only command such as `/summary` -> "That command is only available to the bot owner."
- Non-owner private ordinary message -> relay to owner.
- Group messages -> never match private owner or non-owner command handlers.

### 5. Good/Base/Bad Cases

- Good: register `Command("start", "help")` with `PrivateNonOwnerFilter(owner_id)` in the admin router before the private-user catch-all router.
- Base: keep owner `/start` and `/help` behavior unchanged when adding non-owner guidance.
- Bad: letting non-owner `/start` fall through to `handle_private_user_message`, because it forwards command text to the owner.

### 6. Tests Required

- Unit tests for non-owner guidance response text.
- Unit tests proving owner users are not handled by non-owner guidance.
- Router registration tests proving non-owner guidance covers both `start` and `help`.
- Private relay regression tests must continue to prove ordinary private messages are forwarded.

### 7. Wrong vs Correct

#### Wrong

```python
router.message.register(handle_user_help, Command("help"), PrivateNonOwnerFilter(owner_id))
```

This leaves non-owner `/start` to fall through to the private relay catch-all.

#### Correct

```python
router.message.register(handle_user_help, Command("start", "help"), PrivateNonOwnerFilter(owner_id))
```

Handle both third-party onboarding commands directly before the private relay router can forward them.
