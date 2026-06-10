# WebUI 管理配置中心原型 PRD

## Goal

定义 summary-relay-bot 的 Web 管理配置中心的前端层:信息架构、页面布局、配置项呈现、权限边界、视觉风格与交互。

本阶段交付目标是**静态高保真原型方向**(验证页面结构与视觉),不锁定前端技术栈,不在本任务内实现前端代码。后端数据模型、API 能力边界、安全语义沿用已归档的《Web 管理配置中心 PRD》(`.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`),本 PRD 不重复定义,只在交互层引用其约束。

## Current Context

- 后端配置数据模型已落地于 `src/summary_relay_bot/db/models.py`:`bot_instances`、`llm_providers`、`summary_profiles`、`group_summary_settings`、`audit_logs`,以及带 provenance 字段的 `summary_jobs` / `summary_results`。
- 运行时配置读取已接入(`src/summary_relay_bot/services/runtime_config.py`、`src/summary_relay_bot/main.py`):启动时从 DB 读取 enabled bot、解密 token、创建 Bot、注册路由、启动 polling。
- 安全边界已定:单 token 认证(`WEBUI_ADMIN_TOKEN`,常量时间比较,失败 401 不泄露细节);secret 只可替换、不可查看明文;API/日志/审计统一脱敏。
- 唯一约束已定:同一时间只允许一个 enabled bot、一个 default summary profile;同群组同时只允许一个 running summary job。
- 群组来源:bot 被拉进群后由 `group_collection` 服务自动发现入库(`groups.discovered_at`),不在 WebUI 内手动新建。
- 归档 PRD 明确把"页面信息架构、布局、视觉、交互"留待原型阶段补充,即本任务。

## Scope

### In Scope

- WebUI 信息架构与一级导航。
- 各页面布局形态与核心配置项呈现方式。
- 关键交互:secret 字段、验证/测试、需重启生效提示、互斥约束确认、手动触发摘要的异步反馈。
- 认证入口形态与 token 存储策略。
- 视觉风格基调与状态色规范。
- 交付物:静态高保真原型方向(页面结构 + 视觉),供后续实现参考。

### Out of Scope

- 前端技术栈选型与前端代码实现(SPA / 模板+htmx 等,后续单独决策)。
- 后端数据模型、API 路由、安全语义的重新定义(沿用归档 PRD)。
- 多管理员、用户名密码、RBAC、session cookie。
- 多 bot 同时 polling、bot token 在线热切换、LLM 自动 fallback、成本统计。
- 公网部署、HTTPS、反向代理的完整方案。

## Product Positioning

- v1 核心场景:**配置管理为主**(非监控大盘、非首次初始化向导、非纯排障工具)。
- 使用环境:**桌面为主 + 移动可查看**。桌面采用信息密度较高的后台布局;关键页面(状态查看、手动触发摘要)需在手机上可用 → 可折叠侧边栏 + 单列自适应卡片/表单。

## Information Architecture

一级导航共 5 条,摘要引擎内部用 tab 区分 Provider 与 Profile(二者依赖链紧、常一起配):

```
侧边栏(5 条)            首页 = 轻量状态 Dashboard
├ Dashboard             状态卡 ×4
├ Bot                   快捷入口区
├ 摘要引擎
│  ├ LLM Provider (tab)
│  └ Summary Profile (tab)
├ 群组
└ 审计日志
```

配置对象依赖链:`LLM Provider ← Summary Profile ← 群组绑定`。导航顺序按"先有能力、再绑群组"的心智排列。

## Pages

### P1. Dashboard(首页)

- 形态:**轻量状态卡 + 快捷入口**。目标是一眼看到"现在能不能正常出摘要"。
- 顶部状态卡 ×4:
  1. Bot 运行/验证状态(能否出摘要)。
  2. 启用群组数量。
  3. 默认 Summary Profile(名称 + 是否就绪)。
  4. 最近一次摘要成败。
- 顶部汇总条:当存在待重启生效的配置变更时,显示「有 N 项配置待重启生效」(可展开看是哪些项)。
- 快捷入口:手动触发摘要、查看审计、配置 Provider。
- 移动端:状态卡降为单列堆叠。

### P2. Bot

- 形态:单实例详情(v1 同一时间只允许一个 enabled bot)。
- 展示字段:名称、owner id、telegram username/bot id、enabled、验证状态 + 最近验证时间。
- secret 字段(bot token):见 I1。
- 改 bot token / owner id:见 I3(需重启生效)。
- 启用另一个 bot:见 I4(互斥确认)。
- 验证/测试:见 I2。

### P3. 摘要引擎(LLM Provider / Summary Profile 两个 tab)

- 形态:**卡片网格**(数量通常较少,卡片比表格更直观,也契合卡片化视觉基调)。
- LLM Provider 卡:名称、provider 类型、default model、状态灯、`[测试] [编辑]`。
- Summary Profile 卡:名称、关联 provider、model(覆盖标记)、prompt version、默认标记、`[编辑] [设为默认]`。
- 新增:网格中的 `+` 卡。
- API key(Provider):见 I1。
- 测试连接(Provider):见 I2。
- 设为默认(Profile):见 I4(互斥确认)。
- 移动端:网格降为单列。

### P4. 群组

- 形态:**只读列表 + 详情页**。
- 来源:**只读发现**,无"新增群组"按钮。空列表时提示「把 bot 拉进群组后会自动出现在这里」。
- 列表行(只放最关键列):群名、启用开关、间隔、绑定 Profile、最近摘要状态。
- 详情页承载:群组状态、摘要设置表单(启用 / interval_minutes / 绑定 profile / timezone)、最近摘要历史、手动触发。
- 手动触发摘要:见 I5。

### P5. 审计日志

- 形态:**时间线流**(变更叙事)。
- 每条一句话描述:「<actor> 在 <时间> <动作> <对象>」(例:「panden 在 06-10 14:22 替换了 Provider「主力」的 API key」)。
- 点开看脱敏后的 before/after 对比。
- 过滤器:按 entity_type、action、时间范围。
- 数据来源:`audit_logs`(actor / action / entity_type / entity_id / redacted_before / redacted_after / created_at)。

## Key Interactions

### I1. Secret 字段(bot token / Provider API key)

- 呈现:**掩码占位符 + 输入框**。已配置时显示「已配置」标签 + 掩码占位符。
- 语义:**输入新值 = 替换;留空 = 不修改**。字段旁明示该语义。
- 不可查看明文(沿用后端约束)。
- ⚠️ 防误清空:提交时空值必须按"不修改"处理,绝不可把空值当作"清空 secret"提交。

### I2. 验证 / 测试连接

- 呈现:**状态灯 + 手动测试**。状态灯取值:未验证 / 有效 / 无效 / 错误(对应 `status` 字段),旁附最近验证时间。
- 操作:`[测试]` 按钮手动触发,就地刷新状态。
- 错误(invalid / error)原因可展开查看,便于排查。

### I3. 需重启生效提示

- 适用:改 bot token、改 owner id(v1 不做在线热切换)。
- 呈现:**字段级"待重启"徽章(警告橙) + Dashboard 顶部汇总「N 项待重启生效」**。
- 重启后徽章与汇总消失。
- 原因(已确认,写入 PRD 以免后续误解):
  - bot token 在启动时被 `create_bot()` 烘焙进 aiogram Bot 对象,polling 在固定 Bot 上运行,运行中无重载路径。
  - owner_id 在 `register_routers` 阶段构造进各过滤器(`OwnerPrivateFilter` / `PrivateNonOwnerFilter`),路由表建好后运行中不重读。
  - 启动链路 `读 DB → 解密 → 建 Bot → 注册路由 → 启动 polling` 是单向的,无配置变更监听回路。
  - 在线热切换属归档 PRD 的 Out of Scope。

### I4. 互斥约束确认

- 适用:启用另一个 bot(顶掉当前 enabled bot)、设另一个默认 Profile(顶掉当前默认)。
- 呈现:操作时弹确认弹窗,明确说明会顶掉当前项及其影响。

### I5. 手动触发摘要(异步)

- 异步任务,状态:pending / running / succeeded / failed / blocked。
- 呈现:**按钮原地轮询状态**。点「触发」→ 按钮变「生成中…」并轮询 job → 完成后原地显示「✓ 已生成」或「✗ 失败」。
- 失败可展开看 `error_type` / `error_message`。
- 并发约束:同群组已有 running job 时,触发按钮置灰并提示「该群有摘要正在生成」(对应 `summary_jobs` 同群组 running 唯一约束)。

## Auth & Permission Boundary

- 单 token 认证,token 来自 `WEBUI_ADMIN_TOKEN`,常量时间比较,失败返回 401 且不泄露细节(沿用后端约束)。
- 入口形态:**极简 token 登录页**(单输入框)。认证成功后请求携带 `Authorization` 头。
- token 存储:**`sessionStorage`**(关闭页面即失效,降低持久化与 XSS 风险)。v1 不提供"记住我"持久化。
- 认证错误统一提示「认证失败」,不区分 token 长度 / 接近程度。
- v1 无用户名密码、无多管理员、无 RBAC。

## Visual Style

- 风格参考:Semi Design / 字节企业后台 / Linear / Vercel Dashboard。
- 背景:白 + 极浅灰,大量留白。
- 布局:卡片化,12–16px 圆角、1px 浅色边框、轻微阴影。
- 主色:蓝紫 / 紫色渐变,用于按钮、选中态、关键数据强调。
- 图标:轻量线性图标,避免厚重拟物。
- 字体层级:标题偏粗,正文克制,辅助信息浅灰。
- 状态色(柔和、低饱和):成功绿 / 警告橙 / 错误红。
  - 状态灯(I2)与"待重启"徽章(I3,用警告橙)沿用此色阶。

## Acceptance Criteria

- [ ] 一级导航为 5 条,摘要引擎内含 Provider / Profile 两 tab。
- [ ] 首页为轻量状态 Dashboard,含 4 张状态卡 + 待重启汇总 + 快捷入口。
- [ ] Bot 页、摘要引擎页、群组页、审计页形态符合 P2–P5 定义。
- [ ] secret 字段采用掩码占位符 + 输入框,空值语义为"不修改",原型中明示。
- [ ] 验证/测试以状态灯 + 手动测试呈现,错误原因可展开。
- [ ] 改 bot token / owner id 有字段级待重启徽章 + Dashboard 汇总。
- [ ] 启用另一 bot / 设另一默认 profile 有互斥确认弹窗。
- [ ] 手动触发摘要按钮原地轮询状态,running 唯一约束有置灰提示。
- [ ] 认证为极简 token 登录页,token 存 sessionStorage。
- [ ] 视觉风格符合浅色卡片化 + 蓝紫主色 + 柔和状态色规范。
- [ ] 桌面为主、关键页面移动端可用(单列自适应)。
- [ ] 交付静态高保真原型方向(页面结构 + 视觉),未锁定前端技术栈。

## Open Questions

- 已决策:真实 WebUI 实现采用 React + TypeScript + Semi Design + Vite;后端采用 FastAPI `/api/*`;生产保持 Python 单体部署,同时提供 API 和 Vite build 后的静态资源。
- 已决策:Dashboard 首期以状态汇总为主,趋势/分布图可用 VChart / VisActor 支撑,但不把本项目扩展为监控大盘。
- 已决策:摘要历史首期在群组详情页展示最近 N 条,不先做复杂历史检索页。

## Post-Prototype Implementation Plan

原型确认后的真实 WebUI 落地计划已拆分到以下文件:

- [`implementation/plan.md`](implementation/plan.md):总执行计划、技术决策、目录规划、全局接口约定、全局门禁。
- [`implementation/batch-01-web-api-auth.md`](implementation/batch-01-web-api-auth.md):Web API 骨架与认证。
- [`implementation/batch-02-bot-config-api.md`](implementation/batch-02-bot-config-api.md):Bot 配置 API。
- [`implementation/batch-03-engine-api.md`](implementation/batch-03-engine-api.md):LLM Provider / Summary Profile API。
- [`implementation/batch-04-groups-jobs-audit-api.md`](implementation/batch-04-groups-jobs-audit-api.md):Group / Summary Job / Audit API。
- [`implementation/batch-05-frontend-app.md`](implementation/batch-05-frontend-app.md):前端工程初始化与页面落地。
- [`implementation/batch-06-deploy-smoke-docs.md`](implementation/batch-06-deploy-smoke-docs.md):单体部署、Smoke Test 与文档。

执行原则:

- 先后端 API 安全边界,再前端页面。
- 每个批次独立验收、独立回滚。
- 不把多管理员、RBAC、在线切换 Bot token、LLM fallback、成本统计纳入 v1。

## Decision (ADR-lite)

### Context

后端配置数据模型、运行时读取、安全语义均已就绪,归档 PRD 刻意把 WebUI 页面层留待原型阶段。需要先锁定信息架构、页面形态、关键交互与视觉,再决定前端实现。

### Decision

WebUI 以"配置管理"为核心场景,桌面为主 + 移动可查看;5 条一级导航(Dashboard / Bot / 摘要引擎 / 群组 / 审计);首页为轻量状态 Dashboard;Provider/Profile 用卡片网格,群组用列表+详情,审计用时间线流;secret 用掩码占位符+替换语义;需重启与互斥状态显式提示;单 token 极简登录 + sessionStorage;浅色卡片化 + 蓝紫主色视觉。本阶段交付静态高保真原型方向,前端技术栈后续再定。

### Consequences

- 优点:页面结构与交互边界清晰,直接对齐已有后端能力与安全约束;原型可独立验证视觉与结构,不被技术栈绑死。
- 成本:静态原型与最终实现之间存在一次落地转换;部分异步/轮询交互在静态原型中只能示意。
- 风险:secret 字段的"空值=不修改"语义若实现时疏忽,可能误清空,需在实现阶段重点保障。

## Technical Notes

- 后端参考文件:
  - `src/summary_relay_bot/db/models.py`(配置数据模型)
  - `src/summary_relay_bot/services/runtime_config.py`、`src/summary_relay_bot/main.py`(运行时读取与启动链路、需重启原因)
  - `src/summary_relay_bot/handlers/admin.py` 等(owner_id 过滤器注册)
- 归档参考 PRD:`.trellis/tasks/archive/2026-06/06-10-web-config-center-prd/prd.md`(API 能力边界、安全语义、数据表设计)。
- 本 PRD 不定义前端代码与技术栈,仅定义页面层需求,供后续原型与实现任务引用。
