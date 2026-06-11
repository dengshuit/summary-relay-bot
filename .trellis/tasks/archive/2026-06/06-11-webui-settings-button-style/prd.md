# 统一配置页按钮风格

## Goal

让 Bot、摘要引擎、群组、群组详情和审计日志等配置/运维页面的按钮视觉语言与首页 Dashboard 保持一致，减少 Semi UI 默认按钮与首页自定义 `.btn` 风格之间的割裂感。

## What I Already Know

* 用户反馈：配置界面（bot、摘要、群组、审计日志）的按钮风格没有和首页统一。
* 首页 Dashboard 的主要按钮使用原生 `button`/`Link` + `.btn`、`.btn-primary`：固定高度、8px 圆角、粗字重、轻描边、主按钮紫色/悬停色、图标 16px。
* 配置页按钮主要来自 Semi UI `Button`，当前只对 `.page-refresh-button`、`.compact-card-actions .semi-button`、`.modal-actions .semi-button` 做了局部圆角/字重覆盖，覆盖范围不完整。
* 目标页面包括 `web/src/pages/Bot.tsx`、`Engine.tsx`、`Groups.tsx`、`GroupDetail.tsx`、`AuditLogs.tsx`；主要修复点集中在 `web/src/styles.css`。

## Assumptions

* 以首页 `.btn` / `.btn-primary` 作为视觉基准，不重做首页。
* 本任务只调整按钮外观和必要 class 标记，不修改业务行为、API、表单逻辑或文案。
* Semi Button 的 `theme="solid" type="primary"` 对应首页主按钮；普通 Semi Button 对应首页次按钮。

## Requirements

* 页面头部刷新、新增、测试、保存、筛选、加载更多、返回、表格行操作、卡片操作和弹窗 footer 按钮应共享首页按钮的基本尺寸、圆角、字重、图标间距、边框和 hover 风格。
* 主按钮应使用项目主色和 hover 色，并带有与首页 `.btn-primary` 一致的轻阴影。
* 小按钮保持紧凑，但仍采用同一视觉语言。
* 禁用和 loading 状态不能被 CSS 覆盖成看似可点击。
* 不影响输入框、选择器、导航按钮、重启 banner 的非按钮样式。

## Acceptance Criteria

* [ ] 配置/运维页面的 Semi Button 外观看起来与首页 `.btn` / `.btn-primary` 属于同一套系统。
* [ ] Bot、摘要引擎、群组、群组详情、审计日志页面中常见按钮类型都被覆盖。
* [ ] 移动端窄屏下按钮不会因文字溢出破坏布局。
* [ ] `npm run typecheck` 通过。
* [ ] `npm run build` 通过，或说明无法执行原因。

## Out of Scope

* 不新增设计系统组件库。
* 不重构页面结构。
* 不调整后端 API 或数据模型。
* 不处理与按钮无关的视觉问题。

## Technical Notes

* 前端入口：`web/src/main.tsx`，全局样式：`web/src/styles.css`。
* Semi UI 组件集中从 `web/src/ui/semi.ts` 导出。
* 当前前端脚本在 `web/package.json`：`typecheck`、`build`。
