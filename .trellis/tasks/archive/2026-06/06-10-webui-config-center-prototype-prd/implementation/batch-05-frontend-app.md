# Batch 05: 前端工程初始化与页面落地

## 目标

用 React + TypeScript + Semi Design + Vite 实现真实 WebUI,把 `prototype/` 中确认的信息架构、页面结构和关键交互落到生产前端工程。`prototype/` 只作为参考,不复用其静态 CSS 作为生产实现。

## 依据

- WebUI 原型 PRD:5 个一级导航、Dashboard、Bot、摘要引擎、群组、审计日志。
- 原型 `login.html`:token 登录、`sessionStorage`。
- 原型 `index.html`:Dashboard、待重启汇总、状态卡、趋势/分布图。
- 原型 `bot.html`:Bot 表单、secret 替换、测试连接、待重启提示。
- 原型 `engine.html`:Provider/Profile tab、卡片网格、编辑弹窗、设默认确认。
- 原型 `groups.html`、`group-detail.html`:群组列表、详情、摘要设置、手动摘要。
- 原型 `audit.html`:审计时间线。
- 后端 API 批次 01-04 的接口合同。

## 改动范围

- 新增 `web/` 工程。
- 前端依赖:
  - React
  - TypeScript
  - Vite
  - Semi Design
  - Semi Icons
  - React Router
  - VChart / VisActor React binding
- 前端页面:
  - `Login`
  - `Dashboard`
  - `Bot`
  - `Engine`
  - `Groups`
  - `GroupDetail`
  - `AuditLogs`
- 前端组件:
  - `AppShell`
  - `SecretInput`
  - `StatusBadge`
  - `RestartBanner`
  - `ConfirmAction`
  - `JobStatusButton`
- API client:
  - 自动添加 Bearer token。
  - 401 清 token 并跳转登录页。
  - 统一错误 toast。

## 页面落地顺序

1. Login + AppShell
2. Bot
3. Engine
4. Groups + GroupDetail
5. AuditLogs
6. Dashboard 图表和汇总

## 关键前端语义

### 登录

- token 存 `sessionStorage`。
- 关闭页面即失效。
- 不提供记住我。
- 认证失败统一显示“认证失败”。

### SecretInput

- 已配置时显示“已配置”标签和掩码占位符。
- 输入新值才提交替换字段。
- 留空时请求体不发送 secret 字段,或发送空值但后端按不修改处理。
- 不提供查看明文。

### needs_restart

- Dashboard 显示汇总 banner。
- Bot 页显示字段级待重启提示。
- 文案说明 v1 不做在线热切换,重启服务后生效。

### 互斥确认

- 启用另一个 bot 前弹确认。
- 设置默认 profile 前弹确认。
- 前端确认只做 UX 提示,后端仍必须兜住唯一约束。

### 手动摘要

- 点击后按钮进入 running/polling 状态。
- 轮询 `GET /api/groups/{id}/summary-jobs/{job_id}`。
- 终态显示 succeeded/failed/blocked。
- 409 active job 时按钮置灰并显示“该群有摘要正在生成”。

## 明确不做

- 不继续扩展 `prototype/assets/styles.css`。
- 不做营销落地页。
- 不做多管理员或 RBAC。
- 不做 LLM fallback、成本统计。
- 不引入独立前端部署。

## 验收标准

- 一级导航为 Dashboard / Bot / 摘要引擎 / 群组 / 审计日志。
- 摘要引擎内含 LLM Provider / Summary Profile 两个 tab。
- 页面视觉符合浅色卡片化、蓝紫主色、柔和状态色。
- secret 字段统一复用 `SecretInput`。
- Bot 页显示验证状态和待重启。
- Provider/Profile 页面支持新增、编辑、测试、设默认确认。
- 群组页无新增按钮。
- 群组详情支持摘要设置保存和手动摘要轮询。
- 审计日志支持过滤和 before/after 展开。
- 移动端关键页面可用。

## 测试建议

```bash
cd web
npm run typecheck
npm run build
```

如本批次引入前端测试:

```bash
cd web
npm run test
```

## 回滚边界

回滚本批次应移除 `web/` 前端工程和前端构建配置,不影响已完成的后端 API。

