# WebUI 配置中心真实落地计划

## 结论

下一阶段按 6 个批次落地:

1. Web API 骨架与认证
2. Bot 配置 API
3. LLM Provider / Summary Profile API
4. Group / Summary Job / Audit API
5. 前端工程初始化与页面落地
6. 单体部署、端到端 smoke test 与文档

执行顺序固定为先后端安全边界,再业务 API,再 React WebUI,最后部署与 smoke test。不要把多个批次合并成一个大 PR。

## 依据

- 静态原型:
  - `prototype/index.html`
  - `prototype/login.html`
  - `prototype/bot.html`
  - `prototype/engine.html`
  - `prototype/groups.html`
  - `prototype/group-detail.html`
  - `prototype/audit.html`
  - `prototype/assets/styles.css`
  - `prototype/assets/app.js`
- WebUI 原型 PRD:
  - `.trellis/tasks/06-10-webui-config-center-prototype-prd/prd.md`
- 后端配置中心 PRD:
  - `.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`
- 数据模型:
  - `src/summary_relay_bot/db/models.py`
- 已有运行时配置服务:
  - `src/summary_relay_bot/services/runtime_config.py`
  - `src/summary_relay_bot/main.py`

## 技术决策

- 前端采用 React + TypeScript + Semi Design + Vite。
- 图表首选 VChart / VisActor;仅用于 Dashboard 趋势与分布图,不把本项目扩展成监控大盘。
- 后端采用 FastAPI 提供 `/api/*`。
- 生产部署保持单体:同一个 Python 服务提供 Web API 和 Vite build 后的静态资源。
- 认证采用 `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`;token 存在前端 `sessionStorage`。
- v1 不引入多管理员、RBAC、session cookie、在线切换 Bot token、LLM fallback、成本统计。

## 目录规划

后端:

```text
src/summary_relay_bot/web/
  __init__.py
  app.py
  auth.py
  deps.py
  errors.py
  schemas.py
  static.py
  routes/
    dashboard.py
    bot.py
    llm_providers.py
    summary_profiles.py
    groups.py
    audit_logs.py
```

前端:

```text
web/
  package.json
  vite.config.ts
  src/
    api/
      client.ts
      types.ts
    app/
      App.tsx
      routes.tsx
    components/
      AppShell.tsx
      SecretInput.tsx
      StatusBadge.tsx
      RestartBanner.tsx
      ConfirmAction.tsx
      JobStatusButton.tsx
    pages/
      Login.tsx
      Dashboard.tsx
      Bot.tsx
      Engine.tsx
      Groups.tsx
      GroupDetail.tsx
      AuditLogs.tsx
```

## 批次文件

- [Batch 01: Web API 骨架与认证](batch-01-web-api-auth.md)
- [Batch 02: Bot 配置 API](batch-02-bot-config-api.md)
- [Batch 03: LLM Provider / Summary Profile API](batch-03-engine-api.md)
- [Batch 04: Group / Summary Job / Audit API](batch-04-groups-jobs-audit-api.md)
- [Batch 05: 前端工程初始化与页面落地](batch-05-frontend-app.md)
- [Batch 06: 单体部署、Smoke Test 与文档](batch-06-deploy-smoke-docs.md)

## 全局接口约定

### 认证

所有 `/api/*` 默认要求:

```http
Authorization: Bearer <WEBUI_ADMIN_TOKEN>
```

认证失败统一返回:

```json
{
  "error": {
    "code": "unauthorized",
    "message": "认证失败"
  }
}
```

不得暴露 token 是否存在、长度是否接近、格式是否正确等细节。

### 错误格式

```json
{
  "error": {
    "code": "validation_error",
    "message": "interval_minutes must be positive",
    "details": {}
  }
}
```

### Secret 响应

```json
{
  "configured": true,
  "updated_at": "2026-06-10T14:22:00Z"
}
```

### Secret 请求语义

- 字段缺失:不修改。
- `null`:不修改。
- 空字符串:不修改。
- 纯空白字符串:不修改。
- 非空字符串:替换 secret。

v1 不提供查看明文 secret,也不提供清空 secret。

### 状态枚举

```text
validation_status = unvalidated | valid | invalid | error
job_status        = pending | running | succeeded | failed | blocked
provider_type     = anthropic | openai | openai_compatible
```

## 全局验收门禁

每个批次完成前至少确认:

- 当前批次接口或页面符合对应原型/PRD。
- API、日志、审计不泄露 bot token、LLM API key、`WEBUI_ADMIN_TOKEN`、`SETTINGS_ENCRYPTION_KEY`。
- 修改类 API 写 audit log,纯读取不写。
- 后端互斥约束不依赖前端确认弹窗。
- 相关最小测试通过。
- 未实现 PRD 明确排除项。

## 推荐执行策略

- Batch 01 合并后再做 Batch 02。
- Batch 02 和 Batch 03 可以顺序推进,不要并行修改同一批 service 逻辑。
- Batch 04 依赖 Batch 03 的 profile/provider API 和运行时配置语义。
- Batch 05 可以在 Batch 02 后用 mock JSON 起步,但真实合入应等 Batch 04 API 合同稳定。
- Batch 06 在前后端都可运行后执行。

