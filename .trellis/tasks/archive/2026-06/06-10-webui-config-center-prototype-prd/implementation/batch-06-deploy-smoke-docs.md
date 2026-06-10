# Batch 06: 单体部署、Smoke Test 与文档

## 目标

把后端 API、React 静态资源、Docker 构建、README 和端到端 smoke test 串成可交付的单体部署方案。

## 依据

- 后端 PRD R1:bootstrap env 最小化。
- 后端 PRD R7:Web 管理服务随应用启动。
- WebUI 原型 PRD:真实开发需要使用组件库,静态原型只用于确认方向。
- 当前 `Dockerfile`:Python 单阶段镜像。
- 当前 `docker-compose.yml`:单 bot 服务 + Postgres。

## 改动范围

- `Dockerfile`
  - 改为多阶段构建。
  - Node 阶段构建 `web/dist`。
  - Python 阶段复制静态资源,运行时不需要 Node。
- `src/summary_relay_bot/web/static.py`
  - 挂载前端静态资源。
  - `/api/*` 走 API。
  - SPA 路由 fallback 返回 `index.html`。
- `README.md`
- `README.zh-CN.md`
- `docs/operations/telegram-summary-relay-bot.md`
- `web/` 或 `tests/e2e/`
  - Playwright smoke test。

## 部署语义

- 生产仍运行一个 Python 容器。
- Postgres 仍由现有 compose 服务提供。
- WebUI 默认监听 `WEBUI_HOST` / `WEBUI_PORT`。
- `DATABASE_URL`、`SETTINGS_ENCRYPTION_KEY`、`WEBUI_ADMIN_TOKEN` 是 WebUI 必需 bootstrap env。
- Bot token、owner id、LLM API key、LLM model、summary profile、群组摘要配置由数据库管理。

## Smoke Test 覆盖

建议覆盖:

1. 登录页输入 token 后进入 Dashboard。
2. 未认证访问 API 返回 401。
3. Dashboard 可打开。
4. Bot 页保存空 secret 不触发替换。
5. Provider test 按钮能显示状态变化。
6. 设置默认 profile 有确认弹窗。
7. 群组详情手动触发摘要后轮询到终态或 active job 提示。
8. Audit 页面能过滤并展开 before/after。
9. 浏览器刷新 `/groups/:id` 等 SPA 路径仍返回页面。

## 文档更新要点

- 标注 `prototype/` 是静态高保真原型,不参与生产构建。
- 更新必需 env:
  - `DATABASE_URL`
  - `SETTINGS_ENCRYPTION_KEY`
  - `WEBUI_ADMIN_TOKEN`
  - `WEBUI_HOST`
  - `WEBUI_PORT`
- 说明 secret 安全边界:
  - 加密入库。
  - API/日志/审计脱敏。
  - WebUI 只支持替换,不支持查看明文。
- 说明 `needs_restart`:
  - bot token / owner id / enabled bot 变更需要重启。
  - Provider/Profile/Group settings 不需要重启。
- 说明单体部署:
  - 同一 Python 服务提供 Telegram polling、Web API、静态资源。
  - 空 DB 或无 enabled bot 时 WebUI 可启动,polling 不启动。

## 明确不做

- 不引入 Nginx/反向代理完整生产方案。
- 不引入 HTTPS 配置方案。
- 不拆成独立前端服务。
- 不引入多管理员或 RBAC。
- 不做密钥轮换。

## 验收标准

- Docker image build 成功。
- 运行时容器不依赖 Node。
- `/api/dashboard` 可认证访问。
- 前端静态资源可访问。
- SPA 子路由刷新可用。
- README 与实际 env 一致。
- smoke test 通过。

## 测试建议

```bash
python3 -m pytest -q
python3 -m compileall -q src tests migrations
cd web && npm run typecheck && npm run build
docker compose build bot
```

如已引入 Playwright:

```bash
cd web
npm run test:e2e
```

## 回滚边界

回滚本批次应只影响 Docker 构建、静态资源挂载、文档和 smoke test,不改变已完成的业务 API 语义。

