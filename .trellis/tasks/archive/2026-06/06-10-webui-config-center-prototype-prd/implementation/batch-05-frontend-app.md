# Batch 05: 前端工程初始化与页面落地

## Status

已废弃历史实施文档。

本文件描述的是旧 React/Semi WebUI 的首次落地方案，已废弃，不再作为
当前 `web/` 的实现依据。

仍可保留的历史约束只有：

- 登录 token 存储在 `sessionStorage`。
- API 请求使用 `Authorization: Bearer <WEBUI_ADMIN_TOKEN>`。
- Secret 输入为替换语义，留空不修改。
- 前端互斥确认只是 UX，后端必须维护唯一约束。
- 手动摘要触发应遵循后端 summary job 状态流。

旧页面清单、组件清单、Semi Design 依赖和 `web/` 目录规划已移除，避免
误导当前 Web UI 开发。
