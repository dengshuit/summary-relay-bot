# Batch 01: Web API 骨架与认证

## 目标

建立真实 Web API 入口和认证边界,让项目在空数据库或没有 enabled bot 时仍能启动 Web 管理服务。此批次只提供最小 Dashboard 读取能力,不做配置写入。

## 依据

- 后端 PRD R7:空数据库或没有 enabled bot 时 Web 管理服务仍应能启动。
- 后端 PRD R9:Web 管理 API v1 使用 `WEBUI_ADMIN_TOKEN` 单 token 认证。
- 后端 PRD R10:`/api/dashboard` 是必要 API 分组。
- 原型 `login.html`:极简 token 登录页。
- 原型 `index.html`:Dashboard 是 WebUI 首页。

## 改动范围

- `pyproject.toml`
  - 增加 `fastapi`、`uvicorn`。
- `src/summary_relay_bot/web/`
  - `app.py`:创建 FastAPI app。
  - `auth.py`:Bearer token 校验,常量时间比较。
  - `deps.py`:注入 `session_factory`、`SecretService`、actor。
  - `errors.py`:统一错误响应。
  - `schemas.py`:基础响应模型。
  - `routes/dashboard.py`:最小 Dashboard API。
- `src/summary_relay_bot/main.py`
  - 启动 Web 服务。
  - 有 polling resources 时 Web API 与 polling 并行运行。
  - 无 enabled bot 时只启动 Web API,不直接退出进程。
- `tests/`
  - 增加 Web auth 和 dashboard 集成测试。

## 接口

### `GET /api/dashboard`

最小响应:

```json
{
  "telegram_startup": {
    "status": "no_enabled_bot",
    "detail": "no enabled bot instance is configured"
  },
  "bot": null,
  "groups": {
    "total": 0,
    "enabled": 0
  },
  "default_profile": null,
  "summary_24h": {
    "total": 0,
    "succeeded": 0,
    "failed": 0
  },
  "restart_pending": [],
  "recent_audit_logs": []
}
```

## 明确不做

- 不新增 React/Vite 工程。
- 不挂载前端静态资源。
- 不实现 Bot/Provider/Profile/Group 写 API。
- 不实现 Dashboard 趋势图统计。
- 不改变数据模型。

## 验收标准

- 无 token 请求 `/api/dashboard` 返回 401。
- 错 token 返回相同 401 响应,不暴露认证细节。
- 正确 token 返回 200。
- 空数据库可返回可诊断 Dashboard 状态。
- 没有 enabled bot 时 Telegram polling 不启动,Web API 仍可访问。
- 响应、日志、异常中不包含 `WEBUI_ADMIN_TOKEN`、`SETTINGS_ENCRYPTION_KEY`、bot token。

## 测试建议

```bash
python3 -m pytest tests/unit/test_web_auth.py tests/integration/test_web_dashboard.py -q
python3 -m compileall -q src tests migrations
```

## 回滚边界

回滚本批次应只移除 Web API 骨架和 FastAPI 依赖,不影响现有 Telegram polling、DB 模型和摘要逻辑。

