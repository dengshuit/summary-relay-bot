# Web test summary and task progress panel

## Goal

Change the WebUI group-detail summary action into a non-production test summary flow. The Web action should let an administrator test the active summary configuration against recent group messages without changing production summary cursors, without sending Telegram messages, and without creating historical summary records.

## Confirmed Facts

- Current WebUI `立即生成当前摘要` calls `POST /api/groups/{group_id}/summary-jobs`.
- That route creates a `summary_jobs` row, schedules `run_web_manual_summary_job`, polls `/api/groups/{group_id}/summary-jobs/{job_id}`, advances `summary_state.last_summary_sequence` on success, and writes a `summary_results` row.
- The historical summaries page reads from `summary_jobs` joined to `summary_results`, so using those tables creates visible history.
- Scheduled summaries use the production path and should remain unchanged: they summarize messages after the cursor, privately send to the administrator, then advance the cursor and save a result.
- Group detail currently shows a top inline status banner, not a fullscreen loading overlay. The requested UI change is to replace that banner with a card-style progress panel.

## Requirements

- Web-triggered summary is a test-only task.
- The test task summarizes the current group chat's most recent messages, capped at 50 source messages.
- The test task must not advance `summary_state.last_summary_sequence`.
- The test task must not create `summary_jobs` or `summary_results` historical records.
- The test task must not send any Telegram message to the administrator or to the group.
- The test task should use the same group-effective summary profile / LLM runtime config as production summaries.
- The test task should expose asynchronous task state for frontend polling.
- In-memory test task state must be bounded and must not grow without limit.
- The in-memory registry may hold at most 5 tasks.
- Completed, failed, or canceled test tasks expire automatically after 30 minutes.
- When the task registry reaches its maximum entry count, oldest terminal tasks should be evicted first; if still full, task creation should fail safely instead of growing memory unbounded.
- The group detail page should replace the existing inline "该群有摘要正在生成..." banner with a reusable `AsyncTaskProgress` / `TaskProgressPanel` component.
- The progress panel should show these lifecycle steps: `已提交`, `排队中`, `执行中`, `生成结果`, `完成`.
- The current step should use a spinner or pulsing marker, completed steps should use a check icon, and future steps should use muted dots.
- Because the backend does not currently return a percentage, the panel should use an indeterminate progress bar.
- The panel should include helper text: `任务可能需要 1-3 分钟，你可以留在当前页面等待`.
- The panel should support success, error, cancel, and long-running "仍在处理中" display states.
- On success, the UI should automatically show a result dialog/panel containing the generated summary, and also provide a `查看结果` entry from the progress panel.
- On failure, the UI should show the backend error reason and provide a retry action.
- Existing scheduled summary behavior and Telegram admin command summary behavior are out of scope for behavior changes.

## Acceptance Criteria

- [ ] Clicking the WebUI group-detail summary test button starts an async test task and immediately displays the progress panel.
- [ ] The backend test task reads at most 50 most recent group messages, ordered chronologically for summarization.
- [ ] Successful Web test summary returns generated summary text to the frontend.
- [ ] Successful Web test summary does not change the group's `last_summary_sequence` or `last_summary_at`.
- [ ] Successful Web test summary does not create `summary_jobs` or `summary_results` rows.
- [ ] Web test summary does not call Telegram `send_message`.
- [ ] In-memory task registry enforces a finite task count and TTL-based cleanup.
- [ ] If the task registry is full, the API returns a safe conflict/busy response instead of accepting unbounded work.
- [ ] The success UI automatically opens a result dialog/panel and provides a `查看结果` button.
- [ ] Failed test summary displays `error_type` / `error_message` when available and offers retry.
- [ ] A long-running poll does not flip to failure solely due to elapsed time; it displays `仍在处理中` and keeps polling.
- [ ] Frontend typecheck/build passes.
- [ ] Focused backend tests cover no cursor advance, no history rows, 50-message cap, auth, and failure state.

## Out of Scope

- Changing scheduled summary delivery or cursor semantics.
- Changing Telegram `/summary` command behavior.
- Persisting Web test summaries into the historical summaries list.
- Adding multi-process distributed task storage.
- Adding WebSocket/SSE transport; polling is acceptable.

## Open Question

- None. The user accepted process-memory task state with a hard limit of 5 tasks and 30-minute terminal-task expiry.
