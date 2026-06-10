# Batch 03 LLM Provider / Summary Profile API

## Goal

基于已归档的 WebUI 配置中心任务，实现 Batch 03 的后端 API：LLM Provider 读取、新增、最小更新/禁用/测试，以及 Summary Profile 读取、新增、最小更新、设为默认。

## Requirements

- 实现 `GET /api/llm-providers`，支持 `enabled`、`status` 过滤，响应必须脱敏 API key。
- 实现 `POST /api/llm-providers` 和 `PATCH /api/llm-providers/{id}`，API key 遵守“缺失/null/空字符串/纯空白 = 不修改；非空字符串 = 替换”。
- 实现 `POST /api/llm-providers/{id}/test`，更新 provider 状态灯字段。
- 实现 `GET /api/summary-profiles`，响应包含 provider 摘要、effective model、是否使用 provider 默认模型。
- 实现 `POST /api/summary-profiles`、`PATCH /api/summary-profiles/{id}`、`POST /api/summary-profiles/{id}/set-default`。
- 后端强制同一时间只允许一个 default summary profile，不能只依赖前端确认。
- 修改类 API 写 redacted audit log，API key 不得出现在 API 响应、日志、异常、审计中。
- 所有 `/api/*` 继续使用现有 `WEBUI_ADMIN_TOKEN` 认证。

## Acceptance Criteria

- [ ] Provider 列表字段支撑原型卡片。
- [ ] Profile 列表字段支撑默认标记和 model 覆盖标记。
- [ ] API key 加密入库，响应和 audit 不泄露。
- [ ] Provider secret 空值不修改，非空字符串替换。
- [ ] Provider test 更新状态字段。
- [ ] temperature 范围为 `0..2`。
- [ ] `max_output_tokens` 为正数或空。
- [ ] 后端保证唯一默认 profile。
- [ ] 认证保护覆盖 Provider/Profile API。
- [ ] 相关最小 pytest 和 compileall 通过。

## Definition of Done

- 只修改 Batch 03 直接相关后端 API、service、schema、测试。
- 不实现 Group / Summary Job / Audit API。
- 不新增 React/Vite 前端工程，不挂载静态资源，不改 `prototype/`。
- 不实现多管理员、RBAC、session cookie、LLM fallback、成本统计。
- 不改当前摘要执行链路，除非 Batch 03 文档明确要求。

## Technical Approach

- 复用 Batch 01/02 已有 FastAPI app、认证依赖、错误响应、`session_scope` 和 redacted audit log 模式。
- 扩展 `runtime_config.py` 中已有 Provider/Profile service helper，而不是在路由层直接实现业务规则。
- Provider test 采用可 monkeypatch 的 service 边界，单元测试不调用真实外部 LLM 服务。
- 使用现有 SQLAlchemy 模型和 SQLite 测试 fixture，不新增依赖。

## References

- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/batch-03-engine-api.md`
- `.trellis/tasks/archive/2026-06/06-10-webui-config-center-prototype-prd/implementation/plan.md`
- `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`
- `src/summary_relay_bot/services/runtime_config.py`
- `src/summary_relay_bot/web/routes/bot.py`
- `tests/unit/test_web_bot_api.py`
