# Batch 02: Bot 配置 API

## 目标

实现 Bot 页背后的读取、更新、验证能力,并把最敏感的 secret 替换、`needs_restart`、enabled bot 互斥和审计语义做实。

## 依据

- 后端 PRD R2:Bot instance 入库,同一时间只允许一个 enabled bot。
- 后端 PRD R6:Bot token 加密存储,API/日志/审计不泄露明文。
- 后端 PRD R11:替换 bot token、修改 owner id 写 audit log。
- 原型 `bot.html`:Bot 单实例详情、secret 字段、测试连接、待重启提示、启用其他 Bot 互斥确认。
- 模型 `BotInstance`:包含 `status`、`needs_restart`、`last_validated_at`、enabled 唯一索引。

## 改动范围

- `src/summary_relay_bot/web/routes/bot.py`
- `src/summary_relay_bot/web/schemas.py`
- `src/summary_relay_bot/services/runtime_config.py`
  - 补齐 Bot list/get/update/enable/validate service。
  - 复用现有 `SecretService` 和 `create_audit_log`。
- `tests/`
  - Bot API 测试。
  - secret 不泄露测试。
  - `needs_restart` 测试。

## 接口

### `GET /api/bot`

响应:

```json
{
  "active": {
    "id": 1,
    "name": "生产主号",
    "owner_id_redacted": "88***12",
    "telegram_bot_id": 7654321098,
    "telegram_username": "summary_relay_bot",
    "enabled": true,
    "status": "valid",
    "needs_restart": true,
    "last_validated_at": "2026-06-10T14:18:00Z",
    "secret": {
      "configured": true,
      "updated_at": null
    }
  },
  "items": []
}
```

### `PATCH /api/bot`

请求:

```json
{
  "id": 1,
  "name": "生产主号",
  "owner_id": 8812345678,
  "bot_token": "",
  "enabled": true
}
```

语义:

- `bot_token` 缺失、`null`、空字符串、纯空白字符串:不修改。
- 非空 `bot_token`:加密替换,设置 `needs_restart=true`。
- `owner_id` 变更:设置 `needs_restart=true`。
- `enabled=true`:后端自动停用其他 enabled bot,设置 `needs_restart=true`。

### `POST /api/bot/validate`

请求:

```json
{
  "id": 1,
  "bot_token": null
}
```

响应:

```json
{
  "status": "valid",
  "last_validated_at": "2026-06-10T14:18:00Z",
  "telegram_bot_id": 7654321098,
  "telegram_username": "summary_relay_bot",
  "error_type": null,
  "error_message": null
}
```

## 明确不做

- 不支持查看 bot token 明文。
- 不支持清空 bot token。
- 不支持在线热切换 polling Bot。
- 不支持多个 Bot 同时 polling。
- 不实现前端 Bot 页面。

## 审计边界

写 audit:

- `replace_bot_token`
- `update_bot_instance`
- `enable_bot_instance`

可不写 audit:

- 纯读取。
- validate 只更新验证状态时。

audit 中 owner id 脱敏,bot token 只写 `"configured"` / `"not_configured"`。

## 验收标准

- `GET /api/bot` 不返回 bot token 明文。
- `PATCH /api/bot` 空 token 不会清空原 token。
- 替换 token 会加密入库并写脱敏 audit。
- 修改 token、owner id、enabled bot 后 `needs_restart=true`。
- 后端保证同一时间最多一个 enabled bot。
- validate 能更新 `status`、`last_validated_at`、Telegram 身份字段。

## 测试建议

```bash
python3 -m pytest tests/unit/test_web_bot_api.py tests/unit/test_runtime_config.py tests/unit/test_secrets.py -q
python3 -m compileall -q src tests migrations
```

## 回滚边界

回滚本批次应只移除 Bot Web API 和相关 service 扩展,不影响已有启动时读取 enabled bot 的逻辑。

