# Batch 03: LLM Provider / Summary Profile API

## 目标

实现摘要引擎页背后的 Provider/Profile API,支持 Provider 新增/更新/测试、Summary Profile 新增/更新/设默认,并保持 secret 脱敏和唯一默认约束。

## 依据

- 后端 PRD R3:LLM provider 多实例。
- 后端 PRD R4:Summary profile。
- 后端 PRD R6:LLM API key 加密存储,不可查看明文。
- 后端 PRD R11:新增/修改 Provider/Profile、替换 API key、设置默认 Profile 写 audit log。
- 原型 `engine.html`:Provider/Profile 两个 tab、卡片网格、测试连接、编辑弹窗、设默认确认。
- 模型 `LLMProvider`、`SummaryProfile`:provider type、status、enabled、temperature、default 唯一约束。

## 改动范围

- `src/summary_relay_bot/web/routes/llm_providers.py`
- `src/summary_relay_bot/web/routes/summary_profiles.py`
- `src/summary_relay_bot/web/schemas.py`
- `src/summary_relay_bot/services/runtime_config.py`
  - 扩展 provider/profile update/list/test/set-default service。
  - 保持已有 create helper 的审计与加密路径。
- `tests/`
  - Provider API 测试。
  - Profile API 测试。
  - API key 不泄露测试。
  - 默认 profile 互斥测试。

## 接口

### `GET /api/llm-providers`

查询参数:

```text
enabled=true|false
status=unvalidated|valid|invalid|error
```

响应字段:

```json
{
  "items": [
    {
      "id": 1,
      "name": "主力 Claude",
      "provider_type": "anthropic",
      "base_url": "https://api.anthropic.com",
      "default_model": "claude-sonnet-4-6",
      "timeout_seconds": 30,
      "max_retries": 2,
      "enabled": true,
      "status": "valid",
      "last_validated_at": "2026-06-10T14:18:00Z",
      "secret": {
        "configured": true,
        "updated_at": null
      }
    }
  ]
}
```

### `POST /api/llm-providers`

请求:

```json
{
  "name": "主力 Claude",
  "provider_type": "anthropic",
  "base_url": "https://api.anthropic.com",
  "api_key": "secret",
  "default_model": "claude-sonnet-4-6",
  "timeout_seconds": 30,
  "max_retries": 2,
  "enabled": true
}
```

### `PATCH /api/llm-providers/{id}`

请求字段均可选。`api_key` 使用全局 secret 替换语义。

### `POST /api/llm-providers/{id}/test`

响应:

```json
{
  "status": "valid",
  "last_validated_at": "2026-06-10T14:18:00Z",
  "error_type": null,
  "error_message": null
}
```

### `GET /api/summary-profiles`

响应字段:

```json
{
  "items": [
    {
      "id": 1,
      "name": "标准中文摘要",
      "llm_provider": {
        "id": 1,
        "name": "主力 Claude",
        "provider_type": "anthropic"
      },
      "model": null,
      "effective_model": "claude-sonnet-4-6",
      "uses_provider_default_model": true,
      "prompt_version": "v3",
      "system_prompt": "你是群聊摘要助手...",
      "temperature": 0.3,
      "max_output_tokens": 1024,
      "enabled": true,
      "is_default": true
    }
  ]
}
```

### `POST /api/summary-profiles`

请求:

```json
{
  "name": "标准中文摘要",
  "llm_provider_id": 1,
  "model": null,
  "prompt_version": "v3",
  "system_prompt": "你是群聊摘要助手...",
  "temperature": 0.3,
  "max_output_tokens": 1024,
  "enabled": true,
  "is_default": false
}
```

### `PATCH /api/summary-profiles/{id}`

请求字段均可选。`model=null` 表示使用 provider 默认模型。

### `POST /api/summary-profiles/{id}/set-default`

设置指定 profile 为默认,并取消旧默认。

## 明确不做

- 不实现 LLM fallback。
- 不做成本统计。
- 不要求在本批次实现 `openai` / `openai_compatible` 的完整真实调用链。
- 不实现前端摘要引擎页面。

## 审计边界

写 audit:

- `create_llm_provider`
- `update_llm_provider`
- `replace_llm_api_key`
- `create_summary_profile`
- `update_summary_profile`
- `set_default_summary_profile`

API key 只写 `"configured"` / `"not_configured"`。

## 验收标准

- Provider 列表字段支撑原型卡片。
- Profile 列表字段支撑默认标记和 model 覆盖标记。
- API key 加密入库,响应和 audit 不泄露。
- Provider test 更新状态灯字段。
- temperature 范围为 `0..2`。
- `max_output_tokens` 为正数或空。
- 后端保证唯一默认 profile。

## 测试建议

```bash
python3 -m pytest tests/unit/test_web_llm_provider_api.py tests/unit/test_web_summary_profile_api.py tests/unit/test_runtime_config.py -q
python3 -m compileall -q src tests migrations
```

## 回滚边界

回滚本批次应只移除 Provider/Profile API 和 service 扩展,不影响 Bot API 和 Web API 认证骨架。

