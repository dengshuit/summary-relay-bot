# WebUI 配置中心历史落地计划

## Status

部分废弃的历史实施计划。

本计划中的后端 API 批次仍可作为历史上下文参考；前端 Batch 05/06
属于已废弃的旧 React/Semi WebUI 落地方案，不再作为当前 `web/` 的实现
或部署依据。

## 仍可参考

- [Batch 01: Web API 骨架与认证](batch-01-web-api-auth.md)
- [Batch 02: Bot 配置 API](batch-02-bot-config-api.md)
- [Batch 03: LLM Provider / Summary Profile API](batch-03-engine-api.md)
- [Batch 04: Group / Summary Job / Audit API](batch-04-groups-jobs-audit-api.md)

这些后端批次保留的全局约定：

- `/api/*` 默认要求 `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`。
- 认证失败统一返回 `unauthorized` / `认证失败`，不得泄露 token 细节。
- API、日志、审计不得泄露 bot token、LLM API key、`WEBUI_ADMIN_TOKEN`
  或 `SETTINGS_ENCRYPTION_KEY`。
- Secret 字段缺失、`null`、空字符串、纯空白字符串均表示不修改；非空
  字符串表示替换。
- 修改类 API 写 audit log，纯读取不写。
- 后端互斥约束不能依赖前端确认弹窗。

## 已废弃

- [Batch 05: 前端工程初始化与页面落地](batch-05-frontend-app.md)
- [Batch 06: 单体部署、Smoke Test 与文档](batch-06-deploy-smoke-docs.md)

废弃内容包括旧前端目录规划、React/Semi 页面清单、旧 Vite 静态
资源挂载、旧视觉原型落地顺序和相关前端验证命令。当前 Web UI 工作应
从当前 `web/` 源码和当前 API 合同重新确认。
