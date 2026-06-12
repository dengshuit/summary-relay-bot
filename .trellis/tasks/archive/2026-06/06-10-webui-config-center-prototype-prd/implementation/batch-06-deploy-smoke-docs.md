# Batch 06: 单体部署、Smoke Test 与文档

## Status

已废弃历史实施文档。

本文件描述的是旧 React/Semi WebUI 的部署和 smoke test 方案，已废弃。
其中旧静态资源挂载、Docker 前端构建阶段和 Playwright 覆盖建议不再
作为当前 `web/` 的依据。

仍可参考的历史约束：

- `/api/*` 保持后端 API 路由语义。
- `DATABASE_URL`、`SETTINGS_ENCRYPTION_KEY`、`WEBUI_ADMIN_TOKEN` 是 WebUI
  后端能力的关键 bootstrap env。
- Secret 必须加密入库，并在 API、日志、审计中脱敏。
- 空 DB 或无 enabled bot 时，WebUI API 可以启动，Telegram polling 可不启动。

当前部署和 smoke test 应基于当前 `web/` 实现重新制定。
