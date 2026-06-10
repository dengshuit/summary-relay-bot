# Batch 04: Group / Summary Job / Audit API

## 目标

实现群组列表、群组详情、群组摘要设置、手动触发摘要异步 job、审计日志读取。此批次完成原型中群组页、群组详情页、审计页的后端合同。

## 依据

- 后端 PRD R5:群组摘要策略由 `group_summary_settings` 管理。
- 后端 PRD R8:摘要执行链路通过 group settings -> summary profile -> llm provider。
- 后端 PRD R10:需要群组配置、手动触发摘要、审计日志 API。
- 后端 PRD R11:修改群组摘要配置、手动触发摘要写 audit log。
- 原型 `groups.html`:群组只读列表,无新增按钮。
- 原型 `group-detail.html`:摘要设置表单、最近摘要、手动触发、running job 置灰。
- 原型 `audit.html`:审计时间线、entity/action/date 过滤、before/after 展开。
- 模型 `GroupSummarySettings`、`SummaryJob`、`SummaryResult`、`AuditLog`。

## 改动范围

- `src/summary_relay_bot/web/routes/groups.py`
- `src/summary_relay_bot/web/routes/audit_logs.py`
- `src/summary_relay_bot/web/schemas.py`
- `src/summary_relay_bot/services/runtime_config.py`
  - 扩展 group summary settings service。
- `src/summary_relay_bot/services/summary_jobs.py`
  - 暴露适合 Web API 异步触发和状态读取的边界。
- `src/summary_relay_bot/db/repositories.py`
  - 如有必要,补充按 group 查询最近 job/result、active job、audit 分页查询。
- `tests/`
  - Groups API 测试。
  - Summary job API 测试。
  - Audit logs API 测试。

## 接口

### `GET /api/groups`

查询参数:

```text
q=<title keyword>
enabled=true|false
profile_id=<id>
status=succeeded|failed|blocked|none
limit=50
cursor=<opaque cursor>
```

响应:

```json
{
  "items": [
    {
      "id": 1,
      "chat_id": -100123456,
      "chat_type": "supergroup",
      "title": "技术交流群",
      "username": null,
      "discovered_at": "2026-05-29T00:00:00Z",
      "settings": {
        "enabled": true,
        "interval_minutes": 30,
        "summary_profile_id": 1,
        "timezone": "Asia/Shanghai"
      },
      "effective_profile": {
        "id": 1,
        "name": "标准中文摘要"
      },
      "last_summary": {
        "status": "succeeded",
        "finished_at": "2026-06-10T14:30:00Z",
        "error_type": null
      }
    }
  ],
  "next_cursor": null
}
```

### `GET /api/groups/{id}`

返回群组详情、摘要设置、生效 profile、summary state、最近 job/result、active job。

### `PATCH /api/groups/{id}/summary-settings`

请求:

```json
{
  "enabled": true,
  "interval_minutes": 30,
  "summary_profile_id": 1,
  "timezone": "Asia/Shanghai"
}
```

语义:

- `summary_profile_id=null`:不绑定 profile,运行时使用默认 profile。
- `interval_minutes` 必须大于 0。

### `POST /api/groups/{id}/summary-jobs`

响应:

```json
{
  "job": {
    "id": 10,
    "group_id": 1,
    "chat_id": -100123456,
    "trigger_type": "manual",
    "status": "pending",
    "created_at": "2026-06-10T14:30:00Z",
    "started_at": null,
    "finished_at": null,
    "error_type": null,
    "error_message": null
  },
  "poll_url": "/api/groups/1/summary-jobs/10"
}
```

同群组已有 active job 时返回 409:

```json
{
  "error": {
    "code": "summary_job_conflict",
    "message": "该群有摘要正在生成",
    "details": {
      "active_job_id": 9
    }
  }
}
```

### `GET /api/groups/{id}/summary-jobs/{job_id}`

返回 job 当前状态和 result 摘要元信息。

### `GET /api/audit-logs`

查询参数:

```text
entity_type=bot_instance|llm_provider|summary_profile|group_summary_settings
action=<action>
from=2026-06-10T00:00:00Z
to=2026-06-11T00:00:00Z
limit=50
cursor=<opaque cursor>
```

响应:

```json
{
  "items": [
    {
      "id": 1,
      "actor": "webui_admin",
      "action": "replace_bot_token",
      "entity_type": "bot_instance",
      "entity_id": "1",
      "redacted_before": {
        "bot_token": "configured"
      },
      "redacted_after": {
        "bot_token": "configured",
        "needs_restart": true
      },
      "created_at": "2026-06-10T14:22:00Z"
    }
  ],
  "next_cursor": null
}
```

## 明确不做

- 不提供 `POST /api/groups`,群组来源仍是 bot 自动发现。
- 不实现 Redis/Celery/分布式 worker。
- 不做 LLM fallback。
- 不做摘要成本统计。
- 不实现前端页面。

## 手动摘要 job 语义

- API 请求创建 manual job 并返回 `202`。
- 后台执行可先使用进程内 `asyncio.create_task` 或 FastAPI background task。
- 状态枚举沿用模型:`pending | running | succeeded | failed | blocked`。
- 同群组 active job 冲突由后端兜住。
- 成功 job/result 必须记录实际 provider/profile/model/prompt version。

## 审计边界

写 audit:

- `update_group_summary_settings`
- `trigger_summary`

不写 audit:

- 群组列表/详情读取。
- job 轮询读取。
- 审计日志读取。

## 验收标准

- 群组列表字段支撑原型表格。
- 群组详情字段支撑摘要设置、状态概览、最近摘要历史。
- 群组无新增 API。
- group settings 支持不绑定 profile,运行时使用默认 profile。
- 同群组 active job 冲突返回 409。
- 手动 job 可轮询到终态。
- audit logs 支持过滤和分页。
- before/after 全部脱敏。

## 测试建议

```bash
python3 -m pytest tests/unit/test_web_groups_api.py tests/unit/test_web_summary_jobs_api.py tests/unit/test_web_audit_logs_api.py tests/unit/test_summary_jobs.py -q
python3 -m compileall -q src tests migrations
```

## 回滚边界

回滚本批次应只移除 Group/Job/Audit API 和相关查询扩展,不影响已完成的 Bot、Provider、Profile API。

