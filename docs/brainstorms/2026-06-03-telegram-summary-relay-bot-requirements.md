---
date: 2026-06-03
topic: telegram-summary-relay-bot
---

# Telegram Summary Relay Bot Requirements

## Summary

Build a single-admin Telegram Bot that runs with Bot API polling, collects messages from multiple groups for private incremental summaries, and relays private user messages to the administrator with copy-based message preservation. The first version avoids a public webhook, keeps the bot quiet in groups, and prioritizes safe reply routing over advanced support-desk features.

---

## Problem Frame

The administrator needs a bot that can watch multiple Telegram groups without visibly participating, summarize what happened since the last summary, and send the result privately. The same bot also needs to act as a private-message relay: users can message the bot without learning the administrator's account, and the administrator can reply through the bot without exposing their personal account.

The design must preserve two different message-handling intents. Group messages are summarized, so media can be represented as placeholders. Private messages are conversation content, so media should be copied to the administrator as real Telegram messages rather than reduced to placeholders.

---

## Key Decisions

- **Use Bot API polling for v1.** The first version runs without a public HTTPS endpoint. This keeps deployment simple for personal use while leaving webhook migration as a later production hardening step.
- **Optimize for one administrator.** All admin actions are scoped to a configured owner account. Multi-admin roles, teams, and tenant boundaries are deferred.
- **Separate group-summary handling from private-relay handling.** Group media is converted to summary placeholders; private media is copied with Telegram `copyMessage` so the administrator receives the original message shape.
- **Treat Telegram file bodies as out-of-band.** The database stores raw update metadata, message metadata, and reply mappings, but v1 does not download or store media file bodies.
- **Require explicit reply context for admin replies.** The administrator replies to a copied user message or its info card so the bot can route the response to the correct user. Unscoped admin messages are rejected rather than guessed.
- **Advance summary cursors only after delivery succeeds.** If LLM generation or Telegram delivery fails, the summary state must not move forward.

---

## Actors

- A1. Administrator — the single configured owner account that receives summaries, receives private-user messages, and replies through the bot.
- A2. Group Member — a person posting messages in a Telegram group where the bot is present.
- A3. Private User — a person who privately messages the bot and expects the administrator to receive and answer through the bot.
- A4. Telegram Bot — the bot account that receives updates, stores metadata, copies private messages, and sends messages via Telegram Bot API.
- A5. LLM Service — the model provider used to summarize collected group messages.

---

## Requirements

**Runtime and access**

- R1. The bot must run through Telegram Bot API polling in v1 and must not require a public webhook endpoint.
- R2. The bot must support exactly one configured administrator in v1, identified by Telegram user ID.
- R3. Every administrator-only action must enforce the configured administrator ID server-side, regardless of command menu visibility.
- R4. The bot must be able to manage multiple Telegram groups with the same administrator.

**Group collection and summaries**

- R5. The bot must collect messages from groups and supergroups where it is present, keyed by Telegram `chat_id`.
- R6. The bot must remain quiet in groups by default and must not publish summaries to groups or channels in v1.
- R7. The bot must maintain an independent summary cursor per group so each summary starts after that group's previous successful summary.
- R8. The administrator must be able to trigger summaries manually through private bot commands.
- R9. The bot must support scheduled summaries per enabled group, with a configurable interval such as 5 hours.
- R10. Summary results must be sent only to the administrator's private chat with the bot.
- R11. Group text messages must be included in summary input as text.
- R12. Group media messages must be represented in summary input with placeholders such as `[photo]`, `[voice]`, `[document: filename]`, `[video]`, or `[sticker]`, preserving captions when available.
- R13. V1 summary generation may send the full unsummarized interval to the LLM in one request; if that fails due to length or provider failure, the job must fail without cursor advancement.

**Raw update and storage boundaries**

- R14. The bot must persist Telegram raw update JSON for received updates to support debugging, replay, and future message-type expansion.
- R15. Persisting raw updates must not imply storing media file bodies; v1 must not download group media or private relay media by default.
- R16. The bot must store Telegram media metadata when available, such as `file_id`, `file_unique_id`, file name, MIME type, size, caption, and message type.
- R17. If future functionality requires media retention, file bodies should be stored outside the database, with the database holding storage references only.
- R18. The requirements should allow a retention policy for raw update payloads so metadata storage does not grow unbounded.

**Private user relay**

- R19. When a non-admin user privately messages the bot, the bot must relay the message to the administrator.
- R20. Private user messages must be relayed with Telegram `copyMessage` where possible so text, photo, voice, video, document, and similar content retain their Telegram message shape.
- R21. The bot must send an administrator-visible info card for each incoming private-user message, including enough identity context to distinguish the sender.
- R22. The bot must create reply mappings for both the info card and the copied message when possible, so replying to either can route to the correct user.
- R23. The bot must store private-user metadata for users who have messaged the bot.
- R24. The bot must not attempt to initiate private conversations with users who have never interacted with it.
- R25. If copying a private message fails, the bot must record the failure and notify the administrator without attempting to bypass Telegram's content restrictions.

**Administrator replies**

- R26. The administrator must be able to reply to a copied user message or its info card to send a response to the original private user.
- R27. Text admin replies must be delivered to the target user as text messages.
- R28. Media admin replies must be copied to the target user where Telegram supports copying that message type.
- R29. The bot must reject unscoped ordinary admin messages that are not replies to mapped messages and are not recognized commands.
- R30. The bot should provide a text command fallback such as `/reply <user_id> <message>` for sending a new text message to a known private user.
- R31. V1 does not need a persistent current-chat mode where all unscoped admin messages go to the last selected user.

**Command visibility and menus**

- R32. Administrator command menus should be visible only in the administrator's private chat with the bot, using Telegram command scopes where supported.
- R33. Normal private users should see only user-facing commands such as `/start` or `/help`, or no command menu beyond basic help.
- R34. Group chats should not expose group-management command menus in v1.
- R35. Hidden commands must still be permission-checked server-side; command visibility is not a security boundary.

---

## Key Flows

- F1. Bot starts with polling
  - **Trigger:** The bot process starts.
  - **Actors:** A4.
  - **Steps:** Load configuration, connect to storage, register handlers, start polling, and begin receiving Telegram updates.
  - **Outcome:** Updates are routed without requiring a public webhook.
  - **Covers:** R1, R2.

- F2. Group message is collected
  - **Trigger:** A group member sends a message in a group where the bot receives updates.
  - **Actors:** A2, A4.
  - **Steps:** Persist the raw update, identify the chat as group or supergroup, extract message metadata, convert media to summary placeholders, and store the message for future summaries.
  - **Outcome:** The message is available for summaries and the bot does not reply in the group.
  - **Covers:** R5, R6, R11, R12, R14, R16.

- F3. Scheduled summary runs
  - **Trigger:** A group's configured interval elapses.
  - **Actors:** A4, A5, A1.
  - **Steps:** Create or run a summary job, read messages after that group's last successful cursor, send the interval to the LLM, private-message the summary to the administrator, then advance the cursor only after successful delivery.
  - **Outcome:** The administrator receives a private summary and the group cursor advances safely.
  - **Covers:** R7, R9, R10, R13.

- F4. Administrator manually triggers a summary
  - **Trigger:** The administrator sends a private command such as `/summary` or `/summary <chat_id>`.
  - **Actors:** A1, A4, A5.
  - **Steps:** Verify administrator identity, select all enabled groups or the requested group, run the same summary job path as scheduled summaries, and report results privately.
  - **Outcome:** Manual and scheduled summaries share the same cursor and delivery rules.
  - **Covers:** R3, R8, R10, R13.

- F5. Private user message is relayed to administrator
  - **Trigger:** A non-admin user privately messages the bot.
  - **Actors:** A3, A4, A1.
  - **Steps:** Persist the raw update, update private-user metadata, create a private-message record, send an info card to the administrator, copy the original message to the administrator, and map administrator-side message IDs back to the original user.
  - **Outcome:** The administrator sees who sent the message and receives the original message shape where Telegram copying permits.
  - **Covers:** R19, R20, R21, R22, R23, R25.

- F6. Administrator replies to a private user
  - **Trigger:** The administrator replies to a mapped info card or copied message.
  - **Actors:** A1, A4, A3.
  - **Steps:** Verify administrator identity, read the replied-to message ID, resolve the target user from the reply map, send text or copy media to that user, and record the outgoing private-message result.
  - **Outcome:** The intended private user receives the administrator's response without seeing the administrator's personal account.
  - **Covers:** R26, R27, R28, R29.

---

## Acceptance Examples

- AE1. Scheduled group summary advances only after success
  - **Covers:** R7, R9, R10, R13.
  - **Given:** A group has new collected messages after its last successful cursor.
  - **When:** The scheduled summary succeeds and the administrator receives the summary.
  - **Then:** The group's cursor advances to the last summarized message.

- AE2. Failed summary does not skip messages
  - **Covers:** R7, R13.
  - **Given:** A group has new collected messages after its last successful cursor.
  - **When:** LLM generation or administrator delivery fails.
  - **Then:** The summary job is marked failed and the cursor remains unchanged.

- AE3. Group file does not create database file-body storage
  - **Covers:** R12, R15, R16.
  - **Given:** A group member sends a document.
  - **When:** The bot stores the update and derived message.
  - **Then:** The database contains raw update metadata, media metadata, and a summary placeholder, but not the document body.

- AE4. Private file is copied to administrator
  - **Covers:** R19, R20, R21, R22.
  - **Given:** A private user sends a document to the bot.
  - **When:** The bot relays the message.
  - **Then:** The administrator receives an info card and a copied Telegram document message, and both are mapped back to that user where possible.

- AE5. Reply routes to the correct user among many private users
  - **Covers:** R22, R26, R27, R28.
  - **Given:** Multiple private users have messages copied into the same administrator-bot chat.
  - **When:** The administrator replies to one mapped message.
  - **Then:** The bot sends the administrator response only to the user associated with that mapped message.

- AE6. Unscoped administrator message is not guessed
  - **Covers:** R29, R30, R31.
  - **Given:** The administrator sends an ordinary private message to the bot without replying to a mapped user message.
  - **When:** The message is not a recognized command.
  - **Then:** The bot does not forward it to any user and prompts the administrator to reply to a mapped message or use the text fallback command.

- AE7. Normal user cannot run admin commands
  - **Covers:** R3, R32, R33, R35.
  - **Given:** A normal private user manually types an administrator command.
  - **When:** The bot receives the command.
  - **Then:** The command is rejected server-side even if the user guessed the command text.

---

## Success Criteria

- The bot can run in a non-public environment as long as it can reach Telegram Bot API.
- The administrator can see and summarize multiple groups independently.
- Group summaries are private to the administrator and never posted in groups by default.
- Group media does not cause file-body growth in the database.
- Private user media is relayed as real Telegram messages where `copyMessage` supports it.
- The administrator can confidently reply to the correct private user by replying to the mapped message or info card.
- Failed summaries and failed private relays are visible to the administrator and do not silently corrupt cursors or mappings.

---

## Scope Boundaries

- Multiple administrators, roles, and team inboxes are deferred.
- Webhook delivery, Redis queues, and horizontal worker scaling are deferred.
- A web dashboard is deferred.
- Media understanding for summaries is deferred; v1 uses placeholders for group media.
- Downloading, archiving, or externally storing media file bodies is deferred.
- Current-chat mode for administrator replies is deferred because it increases accidental-send risk.
- Public group responses and channel publication are out of scope for v1.

---

## Dependencies / Assumptions

- The administrator can obtain and configure the bot token and administrator Telegram user ID.
- Groups that need ordinary message collection have BotFather privacy mode configured appropriately and the bot re-added if needed.
- The bot process should run as a single polling consumer for one bot token in v1.
- Telegram `copyMessage` availability and restrictions determine which private messages can be copied; v1 should not bypass restrictions by downloading and re-uploading protected content.
- LLM context size may limit direct whole-interval summaries; v1 treats over-limit summaries as failed rather than implementing chunked summarization.
- Raw update retention should be configurable during planning so metadata storage remains bounded.

---

## Outstanding Questions

### Resolve Before Planning

- None.

### Deferred to Planning

- Whether v1 storage should use PostgreSQL from the start or allow SQLite for local-only deployment.
- Whether scheduler, polling receiver, and summary worker run as one process with internal tasks or as separate processes in Docker Compose.
- Exact raw-update retention period.
- Exact admin command list and help text.
- Exact summary prompt and model provider configuration.
