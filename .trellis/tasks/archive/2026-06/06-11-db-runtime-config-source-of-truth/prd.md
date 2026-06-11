# 数据库运行时配置唯一事实源

## Goal

当前项目尚未发布上线，不需要保留 `.env` 业务配置和数据库配置之间的过渡兼容。本任务将运行时业务配置收敛为数据库唯一事实源：Bot、LLM、Summary Profile、群组摘要策略全部从数据库读取和管理；`.env` 只保留启动数据库、解密 secret、WebUI 认证和进程级运维所需配置。

## What I Already Know

- 已归档总体 PRD 要求 `.env` 只保留 bootstrap 配置，Bot token、owner id、LLM API key、LLM model、summary prompt version、群组摘要配置不再以 `.env` 作为长期真相来源。
- 当前代码已经有配置数据模型：`bot_instances`、`llm_providers`、`summary_profiles`、`group_summary_settings`、`audit_logs`，以及带 provider/profile/model/prompt provenance 的 `summary_jobs` / `summary_results`。
- 启动链路已部分接入数据库：`BootstrapConfig` 创建数据库连接和 `SecretService`，从 enabled `BotInstance` 解密 bot token 和 owner id，再创建 Telegram Bot。
- WebUI 手动摘要链路已经使用 `load_summary_profile_runtime_config()` 读取 DB provider/profile 并记录 provenance。
- 仍存在过渡态：
  - `AppConfig.from_env()` 仍要求 `BOT_TOKEN`、`OWNER_ID`、`LLM_API_KEY`。
  - `AppConfig` 仍保留 `llm_provider`、`llm_api_key`、`llm_model`、`llm_timeout_seconds`、`summary_prompt_version`。
  - Telegram `/summary` 和 scheduler 摘要链路仍通过 `AppConfig` 创建 `PrivacyAwareSummaryClient`。
  - `groups.summaries_enabled` / `groups.summary_interval_minutes` 与 `group_summary_settings` 双写共存。
  - scheduler 和 Telegram group settings 命令仍读取旧 `groups` 字段。

## Requirements

- `.env` 只保留 bootstrap 和进程级运维配置。
- 生产启动入口只能使用 `BootstrapConfig.from_env()` + 数据库 runtime config，不再依赖 `AppConfig.from_env()` 的旧业务字段。
- 删除或重命名 `AppConfig` 的旧运行时业务职责；保留的进程配置只允许包含：
  - `database_url`
  - webhook 删除策略
  - raw update retention
  - scheduler timezone / misfire / coalesce
- 移除运行时业务 env 字段：
  - `BOT_TOKEN`
  - `OWNER_ID`
  - `LLM_PROVIDER`
  - `LLM_API_KEY`
  - `LLM_MODEL`
  - `LLM_TIMEOUT_SECONDS`
  - `SUMMARY_PROMPT_VERSION`
  - `SUMMARY_DEFAULT_INTERVAL_MINUTES`
- 因项目未上线，直接修改 ORM、初始 migration、测试 fixture 和文档；不实现旧数据迁移或兼容层。
- 从 `GroupChat` / `groups` 初始 schema 中删除旧字段：
  - `summaries_enabled`
  - `summary_interval_minutes`
- `group_summary_settings` 成为群组摘要 enabled、interval、timezone、summary profile 绑定的唯一事实源。
- Telegram 群组配置命令和 WebUI group settings API 使用同一套服务层。
- scheduler 只从 `group_summary_settings.enabled = true` 的记录构建摘要任务，并使用 `GroupSummarySettings.interval_minutes`。
- Telegram `/summary`、scheduler 定时摘要、WebUI 手动摘要必须走同一条数据库 runtime profile 加载链路：
  1. 获取 group。
  2. 获取 group summary settings。
  3. 获取 group 绑定 summary profile 或默认 profile。
  4. 获取 LLM provider。
  5. 解密 provider API key。
  6. 使用 `SummaryProfileRuntimeConfig` 创建 LLM client。
  7. 执行摘要。
  8. 在 `summary_jobs` / `summary_results` 记录 provider/profile/model/prompt version。
- `PrivacyAwareSummaryClient` 不再接受旧 `AppConfig` LLM 字段，只接受数据库 runtime summary profile 配置或等价明确协议。
- 管理员鉴权、command menu、摘要失败通知使用当前 enabled `BotRuntimeConfig.owner_id`。
- Bot token、owner id、enabled bot 变更仍按现有语义标记 `needs_restart`；重启后生效。
- Secret 安全边界保持不变：Bot token 和 LLM API key 加密入库，API/日志/异常/审计不泄露明文。

## Acceptance Criteria

- [ ] 主入口在缺少 `BOT_TOKEN`、`OWNER_ID`、`LLM_API_KEY` 时仍可用 bootstrap env 启动 WebUI。
- [ ] 空数据库或无 enabled bot 时 WebUI 启动，Telegram polling 不启动，并返回可诊断 startup state。
- [ ] 有 enabled bot 时，bot token 和 owner id 从 DB 解密/读取并用于 Bot、handler 鉴权和 command menu。
- [ ] `groups` ORM 和初始 migration 不再包含 `summaries_enabled` / `summary_interval_minutes`。
- [ ] 群组摘要配置只通过 `group_summary_settings` 读写。
- [ ] `/groups`、`/enable_group`、`/disable_group`、`/set_interval` 与 WebUI group settings API 对同一 DB 配置表生效。
- [ ] scheduler 只为 `group_summary_settings.enabled = true` 的群组创建 job，interval 来自 `group_summary_settings.interval_minutes`。
- [ ] Telegram `/summary`、scheduler 定时摘要、WebUI 手动摘要都通过 `load_summary_profile_runtime_config()` 或同等 DB runtime 加载路径创建 LLM client。
- [ ] 成功或失败的摘要任务在可用时记录实际 provider/profile/model/prompt version；配置缺失、provider 禁用、secret 解密失败等情况写入明确失败状态。
- [ ] `PrivacyAwareSummaryClient` 旧 `AppConfig` 分支被移除，相关测试不再依赖旧 env LLM 字段。
- [ ] README、中文 README、operations 文档不再把旧业务 env 描述为长期配置入口。
- [ ] 相关 Python 单测/集成测试和前端 typecheck/build 通过，或明确说明环境原因和替代验证。

## Definition of Done

- ORM、migration、repositories、services、handlers、scheduler、Web API、tests、docs 完成一致性更新。
- 不保留旧 `.env` 业务配置兼容层。
- 不保留 `groups` 旧摘要字段作为 fallback 或双写目标。
- Secret 脱敏和 audit 行为维持现有安全边界。
- 运行最小相关验证：
  - `python3 -m compileall -q src tests migrations`
  - `python3 -m pytest tests/unit/test_config.py tests/unit/test_runtime_config.py tests/unit/test_group_settings.py tests/unit/test_summary_jobs.py tests/unit/test_scheduler.py -q`
  - `python3 -m pytest tests/unit/test_web_groups_api.py tests/unit/test_web_llm_provider_api.py tests/unit/test_web_summary_profile_api.py -q`
  - `python3 -m pytest tests/integration/test_group_collection.py tests/integration/test_web_dashboard.py -q`
  - `cd web && npm run typecheck && npm run build`

## Technical Approach

1. Refactor config boundary.
   - Keep `BootstrapConfig` for startup.
   - Replace or reduce `AppConfig` to process-level settings only.
   - Remove business runtime fields from env parsing and tests.

2. Remove group settings dual truth.
   - Delete old group summary fields from ORM and initial migration.
   - Replace repository helpers that update old fields with `GroupSummarySettings` helpers.
   - Update fixtures and tests that assert old fields.

3. Unify summary runtime config.
   - Make `run_summary_for_group()` accept `SecretService` and current owner id instead of LLM-bearing `AppConfig`.
   - Reuse the same DB profile loader for Telegram manual summary, scheduled summary, and WebUI manual summary.
   - Record provenance on `SummaryJob` and `SummaryResult` from runtime profile.

4. Update scheduler and handlers.
   - Pass `BotRuntimeConfig` / owner id and `SecretService` through app resources or dispatcher context.
   - Build scheduled jobs from `group_summary_settings`.
   - Keep restart-required semantics for Bot identity changes.

5. Update API/frontend/docs/tests.
   - Ensure Web group list/detail/settings use the new table consistently.
   - Remove old env descriptions from docs.
   - Update unit/integration tests to fail if old config paths return.

## Decision (ADR-lite)

**Context**: The codebase currently has a transitional design where database config models exist, but some runtime paths still rely on old env-backed `AppConfig` and old `groups` columns.

**Decision**: Because the project has not been released, remove the transition layer completely. Database-managed runtime configuration becomes the only source of truth. Initial migration and tests are edited directly instead of adding compatibility migrations.

**Consequences**:
- Implementation is simpler and avoids long-term dual truth bugs.
- Existing local dev databases must be recreated or migrated manually; this is acceptable before release.
- Tests and docs need broader updates because old `AppConfig` and group field assumptions are intentionally removed.

## Out of Scope

- Compatibility migration for existing production data.
- `.env` to database import command.
- Online hot reload for Bot token / owner id changes.
- Multi-bot polling.
- Multi-admin/RBAC/session-cookie auth changes.
- LLM fallback, cost tracking, budgets, provider routing beyond existing provider/profile model.
- Secret plaintext viewing or key rotation.

## Suggested Commit Breakdown

1. `refactor(config): remove legacy runtime env config`
2. `refactor(db): make group summary settings the source of truth`
3. `refactor(summary): route all summary jobs through database runtime config`
4. `test/docs: update database-managed configuration coverage`

## Technical Notes

- Relevant archived PRDs:
  - `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`
  - `.trellis/tasks/archive/2026-06/06-10-db-runtime-config-integration/prd.md`
  - `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/prd.md`
  - `.trellis/tasks/archive/2026-06/06-11-batch-04-groups-jobs-audit-api/prd.md`
  - `.trellis/tasks/archive/2026-06/06-11-batch-06-deploy-smoke-docs/prd.md`
- Relevant code areas discovered during analysis:
  - `src/summary_relay_bot/config.py`
  - `src/summary_relay_bot/main.py`
  - `src/summary_relay_bot/db/models.py`
  - `migrations/versions/20260604_0001_initial_schema.py`
  - `src/summary_relay_bot/db/repositories.py`
  - `src/summary_relay_bot/services/runtime_config.py`
  - `src/summary_relay_bot/services/group_settings.py`
  - `src/summary_relay_bot/services/summary_jobs.py`
  - `src/summary_relay_bot/scheduler.py`
  - `src/summary_relay_bot/llm/client.py`
  - `src/summary_relay_bot/handlers/admin_groups.py`
  - `src/summary_relay_bot/web/routes/groups.py`
  - `src/summary_relay_bot/web/routes/dashboard.py`
  - `src/summary_relay_bot/web/schemas.py`
  - `README.md`
  - `README.zh-CN.md`
  - `docs/operations/telegram-summary-relay-bot.md`
