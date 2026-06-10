# 接入数据库运行时配置

## Goal

将启动链路从单一 `AppConfig.from_env()` 逐步接入为 `BootstrapConfig` + 数据库 `BotRuntimeConfig`。本轮只做第二阶段后端接入：让进程能在只有 bootstrap env 的情况下初始化数据库连接并读取 enabled bot；没有 enabled bot 时不启动 Telegram polling；有 enabled bot 时用解密后的 token 和 owner id 构造 bot、注册 handler、设置 command menu。

## Current Context

- 上一轮已提交 `c1358ea feat: add runtime configuration foundations`。
- 已归档总体 PRD：`.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`。
- 已有 `BootstrapConfig`、runtime config 服务层、secret 加解密服务、配置相关模型和初始 schema。
- 当前 `src/summary_relay_bot/main.py` 仍从 `AppConfig.from_env()` 启动并立即创建 Telegram bot / dispatcher / scheduler。
- 当前 `src/summary_relay_bot/telegram/bot.py:create_bot()` 接收 `AppConfig` 并读取 `bot_token`。
- 当前 handler 注册、command menu、private relay、summary job 等权限边界依赖 `config.owner_id`。
- WebUI 页面原型未提供，本轮不实现页面布局、视觉和前端交互。

## Requirements

- 启动流程读取 `BootstrapConfig`，用 `database_url` 创建 engine/session factory，并用 `SETTINGS_ENCRYPTION_KEY` 构造 `SecretService`。
- 从数据库读取唯一 enabled `BotInstance`，解密 token 并构造运行时配置。
- 空数据库或没有 enabled bot instance 时不启动 Telegram polling。
- 没有 enabled bot 的启动结果必须有清晰、可测试的状态边界；若 WebUI API 尚未实现，先封装为服务/函数并测试。
- 有 enabled bot 时，`create_bot`、handler 注册、command menu 设置使用数据库运行时 token / owner id。
- 不实现多 bot 同时 polling。
- 保留现有 `AppConfig` 测试路径，除非完整替换相关调用链并更新测试。
- secret 明文不得出现在日志、`repr`、错误字符串或审计脱敏数据中。

## Acceptance Criteria

- [ ] `BootstrapConfig` 启动路径可构造数据库资源并读取 runtime bot config。
- [ ] 没有 enabled bot 时返回可诊断状态，并跳过 Telegram polling。
- [ ] enabled bot 能解密 token 并构造可用于 `create_bot` 的运行时配置。
- [ ] owner id 进入 handler 注册和 command menu 权限边界。
- [ ] 运行时配置对象和启动状态的 `repr` / 日志安全，不泄露 bot token。
- [ ] 相关单元测试覆盖 no enabled bot、enabled bot、owner 权限边界、secret 不泄露。

## Out of Scope

- WebUI 页面、布局、视觉、前端交互。
- Web 管理 API 的完整 CRUD。
- 多 bot 同时 polling。
- 旧 `.env` 业务配置导入、旧数据迁移或兼容层。
- LLM provider / summary profile 调用链完整替换。
- 在线切换 bot token 或 owner id。

## Technical Approach

- 保留 `AppConfig`，继续支持现有测试和未迁移链路。
- 新增或调整轻量运行时启动结构，用于表达：
  - 数据库/bootstrap 资源已创建；
  - 是否发现 enabled bot；
  - polling 是否应启动；
  - 若不启动，原因是什么。
- 将 bot token 读取边界从 `AppConfig` 抽象到 `BotRuntimeConfig` 或最小协议，避免 handler/scheduler 仍需要知道 token。
- handler 注册和 command menu 继续只消费 owner id 权限边界，确保 owner id 来自数据库 enabled bot。
- 日志只记录 `BootstrapConfig.safe_dict()` 和运行时状态的脱敏信息，不记录解密 token。

## Definition of Done

- 实现最小后端接入代码。
- 补充/更新相关单元测试。
- 运行可用的相关测试；若依赖缺失，至少运行 `compileall` / import smoke check 并说明缺口。
- 不把 `.agents`、`.codex`、`AGENTS.md`、Trellis bootstrap 未跟踪文件混入代码提交。

## Technical Notes

- 已读取用户指定文件：
  - `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`
  - `src/summary_relay_bot/config.py`
  - `src/summary_relay_bot/main.py`
  - `src/summary_relay_bot/telegram/bot.py`
  - `src/summary_relay_bot/handlers/__init__.py`
  - `src/summary_relay_bot/services/runtime_config.py`
  - `src/summary_relay_bot/services/secrets.py`
- 相关规范：
  - `.trellis/spec/backend/index.md`
  - `.trellis/spec/backend/*.md`
  - `.trellis/spec/guides/code-reuse-thinking-guide.md`
  - `.trellis/spec/guides/cross-layer-thinking-guide.md`

