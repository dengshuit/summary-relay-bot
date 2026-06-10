# Web 管理配置中心 PRD

## Goal

将当前依赖 `.env` 的 Bot 与 LLM 运行配置演进为数据库驱动的管理配置中心，并为后续 Web 管理面板提供清晰的后端能力边界。第一版目标不是做 `.env` 网页编辑器，而是建立可审计、可加密、可运行时读取的配置模型，使 Bot token、owner id、多个 LLM provider、summary profile、群组摘要策略都可以由管理面板统一维护。

WebUI 页面布局、导航结构、组件细节、视觉样式和具体前端交互暂不在本 PRD 中落定，等待用户完成页面原型后补充。

## Current Context

- 当前启动配置集中在 `src/summary_relay_bot/config.py` 的 `AppConfig.from_env()`。
- 当前启动流程在 `src/summary_relay_bot/main.py` 中先读取 env，再创建 Telegram Bot、数据库 engine、scheduler、dispatcher。
- 当前 LLM 客户端 `src/summary_relay_bot/llm/client.py` 依赖 `AppConfig`，并使用单一 Anthropic 配置。
- 当前群组摘要开关和间隔存放在 `groups` 表的 `summaries_enabled`、`summary_interval_minutes` 字段中，并通过 `src/summary_relay_bot/services/group_settings.py` 管理。
- 当前摘要任务在 `src/summary_relay_bot/services/summary_jobs.py` 中使用全局 `AppConfig` 的 `summary_prompt_version`、`llm_model`、`llm_api_key` 等配置。
- 当前项目仍处于开发阶段，不需要兼容既有生产数据，也不要求提供旧 `.env` 配置的自动导入或数据迁移路径。

## Requirements

### R1. Bootstrap 配置最小化

- 系统仍允许从 `.env` 读取启动必需配置。
- `.env` 只保留无法从数据库读取自身所需的 bootstrap 配置：
  - `DATABASE_URL`
  - `SETTINGS_ENCRYPTION_KEY`
  - `WEBUI_ADMIN_TOKEN`
  - `WEBUI_HOST`
  - `WEBUI_PORT`
- Bot token、owner id、LLM API key、LLM model、summary prompt version、群组摘要配置不再以 `.env` 作为长期真相来源。
- 启动日志和配置渲染必须脱敏所有 secret 与敏感身份字段。

### R2. Bot instance 入库

- 新增 Bot instance 数据模型，用于保存 Telegram Bot 运行身份。
- v1 支持数据库中存在多个 Bot instance 记录，但同一时间只允许一个启用的 Bot instance。
- Bot instance 至少包含：
  - 名称
  - 加密后的 bot token
  - owner id
  - Telegram bot id
  - Telegram username
  - enabled 状态
  - 运行/验证状态
  - 是否需要重启生效
  - 最近验证时间
  - 创建/更新时间
- Web 管理能力可以替换 bot token，但不能查看明文 bot token。
- 修改 bot token 后，v1 标记为需要重启生效，不要求在线切换 polling bot。
- 修改 owner id 后，v1 标记为需要重启生效，避免运行中授权状态不一致。

### R3. LLM provider 多实例

- 新增 LLM provider 数据模型，支持配置多个 LLM 连接实例。
- 每个 LLM provider 至少包含：
  - 名称
  - provider 类型
  - base URL
  - 加密后的 API key
  - 默认模型
  - timeout seconds
  - max retries
  - enabled 状态
  - 验证状态
  - 最近验证时间
  - 创建/更新时间
- v1 provider 类型至少预留：
  - `anthropic`
  - `openai`
  - `openai_compatible`
- v1 必须保留现有 Anthropic 摘要能力。
- `openai` 和 `openai_compatible` 可以按阶段实现，但数据模型和服务边界需要支持。
- Web 管理能力可以新增、编辑、禁用、测试 LLM provider。
- LLM API key 只能替换，不能查看明文。

### R4. Summary profile

- 新增 Summary profile 数据模型，用于定义摘要方案。
- 群组不直接绑定 LLM provider，而是绑定 Summary profile。
- Summary profile 至少包含：
  - 名称
  - 关联的 LLM provider
  - 模型，可覆盖 provider 默认模型
  - prompt version
  - system prompt
  - temperature
  - max output tokens
  - enabled 状态
  - 是否默认 profile
  - 创建/更新时间
- v1 支持设置一个默认 summary profile。
- 新启用群组在未指定 profile 时使用默认 summary profile。
- 摘要任务必须记录实际使用的 provider、profile、model、prompt version，保证历史摘要可追溯。

### R5. 群组摘要策略重建

- 新增或重构群组摘要配置模型，用于管理群组级摘要策略。
- 群组摘要策略至少包含：
  - group id
  - enabled 状态
  - interval minutes
  - summary profile id
  - timezone
  - 创建/更新时间
- 当前项目仍处于开发阶段，可以直接替换 `groups.summaries_enabled` 和 `groups.summary_interval_minutes` 的设计，不要求兼容旧数据。
- 最终服务层应统一从新的群组摘要策略读取摘要开关、间隔和 profile。
- 不应长期维护旧字段和新表作为双真相来源。

### R6. 密钥加密与脱敏

- Bot token 和 LLM API key 必须加密存储。
- 加密所需根密钥来自 `SETTINGS_ENCRYPTION_KEY`。
- 数据库中不得保存 secret 明文。
- API 响应、日志、异常信息、审计记录不得包含 secret 明文。
- Web 管理能力只展示：
  - 已配置 / 未配置
  - 最近更新时间
  - 验证状态
- v1 不要求支持查看 secret 明文。
- v1 不要求支持 key rotation，但数据模型设计不应阻断未来增加 key version。

### R7. 运行时配置读取

- 启动流程改为：
  1. 读取 bootstrap config。
  2. 创建数据库 engine 和 session factory。
  3. 从数据库读取 enabled Bot instance。
  4. 解密 bot token。
  5. 创建 Telegram Bot。
  6. 注册 dispatcher、scheduler、handlers。
  7. 启动 polling。
  8. 启动 Web 管理服务。
- 空数据库或没有 enabled Bot instance 时，Web 管理服务仍应能启动，方便首次初始化。
- 没有 enabled Bot instance 时，Telegram polling 不启动。
- Bot token 解密失败或验证失败时，Telegram polling 不启动，Web 管理服务需要能暴露可诊断状态。
- Scheduler 构建 job 时应读取新的群组摘要策略。

### R8. LLM 调用链改造

- 当前 `PrivacyAwareSummaryClient(AppConfig)` 需要改造为基于 LLM provider 和 Summary profile 创建。
- 摘要执行链路应变为：
  1. 获取 group。
  2. 获取 group summary settings。
  3. 获取 summary profile。
  4. 获取 llm provider。
  5. 解密 provider API key。
  6. 创建 LLM client。
  7. 执行摘要。
  8. 记录实际使用的 provider/profile/model/prompt version。
- 当 group 未绑定 profile 时，应使用默认 profile。
- 当无可用默认 profile、provider 禁用、secret 缺失、解密失败或 provider 测试失败时，摘要任务应失败并记录明确错误，不能静默跳过。

### R9. Web 管理认证

- Web 管理 API v1 使用 token 认证。
- 管理 token 来自 `WEBUI_ADMIN_TOKEN`。
- 所有管理 API 默认必须认证。
- token 比较必须使用常量时间比较。
- 认证失败返回 401，不泄露 token 是否接近正确、长度等细节。
- v1 不要求用户名密码、多管理员、RBAC、session cookie。

### R10. Web 管理 API 边界

- 本 PRD 只定义后端 API 能力边界，不定义页面布局和前端原型。
- API 至少覆盖：
  - Dashboard 状态读取
  - Bot instance 读取、更新、验证
  - LLM provider 列表、新增、更新、禁用、测试
  - Summary profile 列表、新增、更新、设为默认
  - 群组摘要配置读取、更新、手动触发摘要
  - 审计日志读取
- 修改类 API 必须写审计日志。
- API 响应必须统一脱敏 secret 字段。

### R11. 审计日志

- 新增 audit log 数据模型，记录 Web 管理面板产生的重要配置变更。
- 审计日志至少记录：
  - actor
  - action
  - entity type
  - entity id
  - 脱敏后的 before
  - 脱敏后的 after
  - created at
- 至少记录以下操作：
  - 替换 bot token
  - 修改 owner id
  - 新增/修改/禁用 LLM provider
  - 替换 LLM API key
  - 新增/修改 Summary profile
  - 设置默认 Summary profile
  - 修改群组摘要配置
  - 手动触发摘要

### R12. 开发阶段 schema 替换策略

- 当前项目仍处于开发阶段，不要求兼容旧 `.env` 业务配置或旧数据库数据。
- 可以直接调整初始 schema、migration 和测试 fixture，使新配置模型成为唯一设计。
- 不需要实现 `.env` 到数据库的一次性导入命令。
- 不需要实现旧字段到新表的数据迁移逻辑。
- 文档只需要说明新的 bootstrap env 和数据库配置模型，不需要提供旧配置迁移步骤。

## Non-Functional Requirements

- 安全：secret 不得明文入库、出现在日志、API 响应、异常、审计记录中。
- 可追溯：摘要结果必须能追溯当时使用的 provider/profile/model/prompt version。
- 可诊断：配置缺失、解密失败、provider 禁用、profile 缺失等状态需要有明确错误。
- 最小实施风险：避免在同一阶段同时大改 WebUI、启动流程、LLM 多 provider、群组策略而无法定位问题。
- 兼容当前行为：现有 Anthropic 摘要能力和群组摘要调度语义应保持。
- 可测试：配置读取、密钥加解密、摘要 profile 解析、认证、审计均应有单元测试或集成测试。

## Out of Scope

- WebUI 页面布局、导航、视觉样式、组件结构和具体前端交互。
- 多管理员账号体系。
- RBAC 权限模型。
- 多 Bot 同时 polling。
- 在线无重启切换 Bot token。
- LLM 自动 fallback。
- LLM 成本统计、预算、限流。
- 将 `DATABASE_URL` 放入 WebUI 管理。
- 管理面板公开部署、HTTPS、反向代理配置的完整方案。
- 查看 secret 明文。
- 密钥轮换。

## Technical Approach

### Configuration model

- 将当前 `AppConfig` 拆分为 bootstrap 配置和运行时数据库配置。
- Bootstrap 配置只负责让服务连接数据库、解密 secret、启动 Web 管理入口。
- Bot、LLM、summary profile、group summary settings 由数据库模型表达。

### Proposed database tables

#### `bot_instances`

建议字段：

- `id`
- `name`
- `bot_token_encrypted`
- `owner_id`
- `telegram_bot_id`
- `telegram_username`
- `enabled`
- `status`
- `needs_restart`
- `last_validated_at`
- `created_at`
- `updated_at`

关键约束：

- v1 同一时间只允许一个 enabled bot。
- `bot_token_encrypted` 不得为空，除非该 bot instance 处于未配置草稿状态。

#### `llm_providers`

建议字段：

- `id`
- `name`
- `provider_type`
- `base_url`
- `api_key_encrypted`
- `default_model`
- `timeout_seconds`
- `max_retries`
- `enabled`
- `status`
- `last_validated_at`
- `created_at`
- `updated_at`

关键约束：

- `provider_type` 限定为受支持值。
- `timeout_seconds` 必须为正整数。
- `max_retries` 必须大于等于 0。

#### `summary_profiles`

建议字段：

- `id`
- `name`
- `llm_provider_id`
- `model`
- `prompt_version`
- `system_prompt`
- `temperature`
- `max_output_tokens`
- `enabled`
- `is_default`
- `created_at`
- `updated_at`

关键约束：

- `llm_provider_id` 引用 `llm_providers.id`。
- v1 同一时间只允许一个 default profile。
- `temperature` 范围需要根据 provider 能力定义，v1 可先使用保守范围。

#### `group_summary_settings`

建议字段：

- `id`
- `group_id`
- `enabled`
- `interval_minutes`
- `summary_profile_id`
- `timezone`
- `created_at`
- `updated_at`

关键约束：

- `group_id` 引用 `groups.id` 且唯一。
- `interval_minutes` 必须为正整数。
- `summary_profile_id` 引用 `summary_profiles.id`。

#### `audit_logs`

建议字段：

- `id`
- `actor`
- `action`
- `entity_type`
- `entity_id`
- `redacted_before`
- `redacted_after`
- `created_at`

### Service layer

建议新增服务：

- `BotConfigService`
- `LlmProviderService`
- `SummaryProfileService`
- `GroupSummarySettingsService`
- `SecretService`
- `AuditLogService`

摘要任务不应直接查询所有配置表。摘要任务应通过服务层获取“某个群组当前可用的 summary profile 和 llm provider”。

### API layer

Web 管理 API 可以后续按原型选择前端实现方式。本 PRD 只要求后端 API 能力存在，并保持脱敏、安全和审计语义。

推荐 API 分组：

- `/api/dashboard`
- `/api/bot`
- `/api/llm-providers`
- `/api/summary-profiles`
- `/api/groups`
- `/api/audit-logs`

### Schema replacement strategy

- 当前项目仍处于开发阶段，因此不要求向后兼容旧数据。
- 可以直接更新初始 schema、Alembic migration、模型和测试 fixture。
- 运行时应只使用新的数据库配置模型，避免旧 env 配置和新 DB 配置并存为双真相来源。
- 如果保留旧字段只是为了降低单个 PR 的改动量，必须在同一任务序列中明确删除或停用旧读取路径。

## Acceptance Criteria

- [ ] 系统可仅依赖 bootstrap env 启动到 Web 管理服务可用状态。
- [ ] 空数据库时 Telegram polling 不启动，但 Web 管理服务可以启动。
- [ ] 配置 enabled Bot instance 后，重启服务可使用数据库中的 bot token 启动 polling。
- [ ] Bot token 加密入库，API、日志、审计、repr 均不泄露明文。
- [ ] 可以配置多个 LLM provider。
- [ ] 可以配置至少一个默认 summary profile。
- [ ] 群组可以绑定 summary profile 并配置摘要间隔。
- [ ] 摘要任务使用群组绑定的 summary profile 和 LLM provider。
- [ ] 摘要 job/result 记录实际使用的 provider/profile/model/prompt version。
- [ ] provider/profile 缺失、禁用、secret 缺失、解密失败时，摘要任务失败并记录明确错误。
- [ ] 所有管理 API 需要 `WEBUI_ADMIN_TOKEN` 认证。
- [ ] 认证失败返回 401，且不泄露认证细节。
- [ ] 修改类管理 API 写入 audit log。
- [ ] 不再要求旧 `.env` 业务配置导入数据库，文档以新配置模型为准。
- [ ] 现有 Anthropic 摘要能力保持可用。
- [ ] 相关单元测试和必要集成测试通过。

## Definition of Done

- 数据模型和 Alembic migration 完成。
- 配置服务层完成，并覆盖核心单元测试。
- secret 加密、解密、脱敏测试完成。
- 启动流程完成 bootstrap config 与数据库 runtime config 分离。
- LLM 调用链支持 provider/profile。
- 群组摘要策略切换到新的配置读取路径。
- Web 管理 API 具备认证、脱敏、审计能力。
- 文档说明新 `.env` 最小配置、数据库配置模型和 secret 安全边界。
- 验证命令通过，至少包括相关 unit tests；如无法跑全量测试，需要说明原因。

## Implementation Plan

### PR1. Bootstrap config 与配置表模型

- 拆分 bootstrap config。
- 新增 Bot、LLM provider、summary profile、group summary settings、audit log 模型。
- 新增 Alembic migration。
- 添加模型约束测试。

### PR2. Secret service 与审计基础设施

- 实现 secret 加密、解密、脱敏。
- 实现 audit log 写入服务。
- 添加敏感值不泄露测试。

### PR3. Bot instance 运行时读取

- 启动流程改为从数据库读取 enabled Bot instance。
- 空数据库时只启动 Web 管理服务，不启动 polling。
- 修改 token/owner id 后标记需要重启。
- 增加 Bot token 验证能力。

### PR4. LLM provider 与 Summary profile

- 实现 LLM provider 服务。
- 实现 summary profile 服务。
- 改造 LLM client 创建方式。
- 保持 Anthropic 路径可用。

### PR5. 群组摘要策略接入

- 将群组摘要开关和间隔改为由 group summary settings 管理。
- Scheduler 和 summary job 使用新的群组摘要策略。
- 摘要 job/result 记录 provider/profile/model/prompt version。

### PR6. Web 管理 API

- 增加 token 认证。
- 增加 Bot、LLM provider、summary profile、group、audit log API。
- 修改类 API 写审计日志。
- API 响应统一脱敏。

### PR7. 文档与开发初始化

- 文档说明新的 bootstrap env 和数据库配置方式。
- 文档说明哪些配置不再建议放入 `.env`。
- 文档说明开发环境如何初始化 Bot instance、LLM provider 和默认 summary profile。

### PR8. WebUI 页面

- 暂不执行。
- 等用户提供页面原型后补充页面 PRD 和具体实现任务。

## Open Questions

- WebUI 页面信息架构、页面布局、具体表单字段排列、视觉设计和交互细节等待用户原型后补充。
- `openai` 与 `openai_compatible` 是否在 v1 同步实现真实调用，还是只先完成模型和服务边界，需要在进入对应 PR 前确认。
- secret 加密库是否引入 `cryptography` 需要在实现前结合依赖策略确认。

## Decision (ADR-lite)

### Context

当前项目将 Bot token、LLM API key、LLM model、summary prompt version 等运行配置集中在 `.env` 中。随着 Web 管理面板和多 LLM provider 的需求出现，`.env` 已不适合作为业务配置真相来源。

### Decision

将 `.env` 收敛为 bootstrap 配置；将 Bot instance、LLM provider、Summary profile、群组摘要策略迁移到数据库；通过 Web 管理 API 管理这些对象；secret 加密存储并统一脱敏；摘要任务通过 group settings -> summary profile -> llm provider 的链路选择实际 LLM。

### Consequences

- 优点：配置可管理、可审计、可扩展到多 provider、多 profile、按群组选择摘要方案。
- 成本：启动流程更复杂，需要处理空数据库、配置缺失、secret 解密失败等状态。
- 风险：Bot token 和 LLM API key 入库后，Web 管理入口成为高权限边界，必须同时实现认证、加密、脱敏和审计。
- 延后项：WebUI 页面设计、自动 fallback、成本统计、多管理员、在线切换 Bot token 后续单独设计。

## Technical Notes

- 相关文件：
  - `src/summary_relay_bot/config.py`
  - `src/summary_relay_bot/main.py`
  - `src/summary_relay_bot/db/models.py`
  - `src/summary_relay_bot/db/repositories.py`
  - `src/summary_relay_bot/llm/client.py`
  - `src/summary_relay_bot/services/summary_jobs.py`
  - `src/summary_relay_bot/services/group_settings.py`
  - `src/summary_relay_bot/scheduler.py`
  - `migrations/versions/20260604_0001_initial_schema.py`
- 当前依赖包括 aiogram、SQLAlchemy async、asyncpg、alembic、APScheduler、httpx、anthropic。
- 如引入 Web API 框架，FastAPI 是与当前 async Python 技术栈较匹配的候选，但本 PRD 不强制在页面原型前完成前端实现。
- 本 PRD 刻意不定义页面布局，以免和后续用户原型冲突。
