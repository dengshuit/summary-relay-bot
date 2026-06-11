# Telegram Summary Relay Bot

[English](README.md)

这是一个个人 Telegram Bot。它会静默监听群组消息，向单个管理员私聊发送增量摘要，并通过 Bot 中转私聊用户消息，让管理员无需暴露个人账号即可回复。

当前版本是基于 polling 的 v1 服务，并带有单进程 WebUI 配置中心。Webhook、多管理员、RBAC、session cookie、Redis 队列、群内公开摘要、媒体转写、媒体文件正文存储都不在 v1 范围内。

## 功能

- 使用 Telegram Bot API polling，不需要公开 webhook 地址
- 单个 Telegram 管理员配置，对所有管理员操作做服务端鉴权
- WebUI 配置中心由同一个 Python 进程提供，和 Bot polling 运行时部署在一起
- 通过 Telegram `chat_id` 发现群组和超级群组
- 默认静默采集；新发现群组默认禁用，必须显式启用
- 群组媒体以占位符进入摘要，例如 `[photo]`、`[voice]`、`[document: filename]`、`[video]`、`[sticker]`
- 对启用的群组生成私聊增量摘要
- 只有 LLM 生成和 Telegram 私聊投递都成功后，摘要游标才会推进
- 支持 `/summary` 和 `/summary <chat_id>` 手动摘要
- 支持按群组配置间隔的定时摘要
- 支持私聊用户消息中转、管理员信息卡、Telegram `copyMessage` 和回复映射
- 管理员可通过映射消息回复，或使用 `/reply <user_id> <message>` 回复私聊用户
- 使用 PostgreSQL 保存元数据、原始 update、摘要任务/结果和投递尝试
- 支持原始 update payload 保留周期，到期仅脱敏 JSON payload，不删除业务元数据
- Bot、LLM Provider、Summary Profile、群组设置和审计日志由数据库管理
- 摘要客户端具备隐私边界，只发送白名单字段，并支持 prompt caching

## 架构

![Summary Relay Bot 架构图](docs/architecture/summary-relay-bot-architecture.png)

## 环境要求

- Python 3.12+
- PostgreSQL 16+
- Docker 和 Docker Compose，用于容器化部署
- 通过 BotFather 获取的 Telegram bot token、管理员 Telegram 数字用户 ID，以及需要在 WebUI 中录入的 LLM API key

## 配置

复制 `.env.example` 为 `.env`，并填写本地或生产环境的安全配置。

```bash
cp .env.example .env
```

必填 bootstrap 变量：

| 变量 | 说明 |
| --- | --- |
| `DATABASE_URL` | Async SQLAlchemy 数据库地址，例如 `postgresql+asyncpg://summary_bot:change-me@postgres:5432/summary_relay_bot`。 |
| `SETTINGS_ENCRYPTION_KEY` | 稳定的部署级加密密钥，用于将 Bot token 和 LLM API key 加密后入库。 |
| `WEBUI_ADMIN_TOKEN` | 单个 WebUI 管理员 bearer token。登录页会把它保存在浏览器 `sessionStorage`。 |
| `WEBUI_HOST` | WebUI/API 监听地址。容器暴露端口时使用 `0.0.0.0`。 |
| `WEBUI_PORT` | WebUI/API 监听端口。 |

Bot token、owner id、LLM API key、provider model、summary profile 和群组摘要设置都属于数据库管理的运行时配置。数据库 schema 初始化后通过 WebUI 配置。空数据库或没有 enabled bot 时 WebUI 仍会启动；只有成功加载并解密 enabled bot 后才会启动 Telegram polling。

用下面的命令生成 `SETTINGS_ENCRYPTION_KEY`：

```bash
python3 -c "from summary_relay_bot.services.secrets import SecretService; print(SecretService.generate_key())"
```

重要可选变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ALLOW_WEBHOOK_DELETE` | `false` | 为 `false` 时，如果 Telegram 仍有 active webhook，启动会失败。 |
| `DROP_PENDING_UPDATES_ON_WEBHOOK_DELETE` | `false` | 除非明确要在删除 webhook 时丢弃 pending updates，否则保持 `false`。 |
| `RAW_UPDATE_RETENTION_DAYS` | `30` | 原始 update JSON payload 保留天数，到期仅脱敏 payload 正文。 |
| `SCHEDULER_TIMEZONE` | `UTC` | 调度器时区。 |
| `SCHEDULER_MISFIRE_GRACE_SECONDS` | `300` | 调度器 misfire 宽限时间。 |
| `SCHEDULER_COALESCE` | `true` | 服务停机恢复后是否合并错过的调度。 |

不要提交真实 token、数据库密码、加密密钥、管理员 token 或 API key。

## 生产部署

生产部署围绕 Docker 镜像和 `docker-compose.yml`。

### 构建并发布 Docker 镜像

`.github/workflows/docker-image.yml` 中的 GitHub Actions workflow 会基于 `Dockerfile` 构建镜像，并发布到 GitHub Container Registry：

```text
ghcr.io/<owner>/<repo>
```

Workflow 行为：

- 推送到 `main` 或 `master` 时，构建并发布镜像。
- 推送匹配 `v*.*.*` 的 tag 时，构建并发布版本镜像 tag。
- Pull request 只构建镜像，不发布。
- 发布的 tag 包含 branch/tag ref、`sha-<commit>`，默认分支还会发布 `latest`。

该 workflow 使用 GitHub 内置的 `GITHUB_TOKEN`。在同一个仓库内发布到 GHCR，不需要额外配置 registry secret。

### 配置生产环境

在部署机器上创建 `.env`：

```bash
cp .env.example .env
```

至少设置以下生产值：

```env
DATABASE_URL=postgresql+asyncpg://summary_bot:replace-with-db-password@postgres:5432/summary_relay_bot
SETTINGS_ENCRYPTION_KEY=replace-with-stable-generated-encryption-key
WEBUI_ADMIN_TOKEN=replace-with-long-random-admin-token
WEBUI_HOST=0.0.0.0
WEBUI_PORT=8080
POSTGRES_PASSWORD=replace-with-db-password
```

使用 compose 内置 PostgreSQL 服务时，`DATABASE_URL` 和 `POSTGRES_PASSWORD` 必须使用同一个数据库密码。

生产镜像是单个 Python 运行时镜像。Docker 构建会先在 Node 阶段执行 `npm ci` 和 `npm run build`，再把 `web/dist` 复制到 Python 镜像中。运行时容器不依赖 Node。

### 使用已发布镜像启动

GitHub Actions 发布镜像后，将 `BOT_IMAGE` 指向 GHCR 镜像 tag：

```bash
export BOT_IMAGE=ghcr.io/<owner>/<repo>:latest
docker compose pull bot
docker compose up -d
```

Docker Compose 的 bot 启动命令会在应用启动前执行 `alembic upgrade head`，因此新数据库会自动迁移。如果迁移失败，bot 容器会退出，不会继续用无效 schema 启动。

一个 bot token 只能运行一个 polling 进程。Telegram polling 和 webhook 互斥；使用 polling 前应取消 webhook，或明确设置 `ALLOW_WEBHOOK_DELETE=true`。

打开 `http://<host>:<WEBUI_PORT>/`，使用 `WEBUI_ADMIN_TOKEN` 登录 WebUI。API 请求统一在 `/api/*` 下；其他构建后的 WebUI 路由会 fallback 到 React SPA，因此刷新 `/groups/<id>` 这类子路由仍可打开页面。

### 生产升级

拉取新镜像并重启 bot。容器会在应用启动前执行待处理迁移：

```bash
export BOT_IMAGE=ghcr.io/<owner>/<repo>:latest
docker compose pull bot
docker compose up -d bot
```

## 开发部署

本地开发优先使用 Python 环境快速迭代；需要容器化运行时使用 Docker Compose。

### 本地 Python 环境

安装包和开发依赖：

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

如果环境不支持 `venv`，可以安装到用户环境：

```bash
python3 -m pip install --user --break-system-packages -e '.[dev]'
```

运行测试：

```bash
python3 -m pytest -q
```

运行编译检查：

```bash
python3 -m compileall -q src tests migrations
```

检查已安装依赖一致性：

```bash
python3 -m pip check
```

### 本地 Docker Compose

创建并编辑 `.env`：

```bash
cp .env.example .env
```

本地构建并启动 bot：

```bash
docker compose up --build bot
```

也可以启动所有服务：

```bash
docker compose up --build
```

Docker Compose 的 bot 启动命令会在启动应用前自动执行迁移。

## 数据库迁移

Docker Compose 会为 bot 服务自动执行迁移。非 Compose 部署首次连接新数据库前，需要先执行迁移：

```bash
alembic upgrade head
```

如需通过 Docker Compose 的 bot 镜像手动执行迁移，可以覆盖服务命令：

```bash
docker compose run --rm bot alembic upgrade head
```

## WebUI 配置中心

WebUI 是单体服务的一部分：同一个 Python 服务在条件满足时运行 Telegram polling，同时提供 `/api/*` 和 `web/dist` 中构建好的 React/Vite 静态资源。`prototype/` 目录只是静态高保真视觉与交互参考，不参与生产构建。

WebUI 使用来自 `WEBUI_ADMIN_TOKEN` 的单 bearer token 认证。前端把 token 保存在 `sessionStorage`；v1 不提供用户名密码、多管理员、RBAC 或 session cookie。

Secret 字段只支持替换：

- Bot token 和 LLM API key 使用 `SETTINGS_ENCRYPTION_KEY` 加密后入库。
- API 响应、普通日志、异常和审计记录必须脱敏。
- WebUI 只展示已配置/未配置状态和更新时间，永不展示明文 secret。
- secret 输入留空表示“不修改”；输入非空值表示替换已保存的 secret。

`needs_restart` 表示当前运行中的 polling 进程尚未加载需要重启才能生效的 Bot 运行配置。替换 Bot token、修改 owner id、启用另一个 Bot 都需要重启服务；LLM Provider、Summary Profile 和群组摘要设置变更不需要重启。

## Telegram 设置

1. 使用 BotFather 创建 bot。
2. 找到管理员 Telegram 数字用户 ID。
3. 登录 WebUI，配置 Bot token 和 owner id。
4. 管理员先在私聊中向 bot 发送 `/start`，再等待摘要或中转通知。
5. 将 bot 加入需要采集的群组。
6. 如果收不到普通群消息，检查 BotFather privacy mode，并在调整后重新把 bot 加入群组。

该 bot 设计上在群内保持静默。摘要和管理响应只发送到管理员私聊。

## 管理员命令

管理员命令只能在管理员与 bot 的私聊中使用。

| 命令 | 说明 |
| --- | --- |
| `/start` | 显示 bot 状态。 |
| `/help` | 显示管理员帮助。 |
| `/groups` | 列出已发现群组、启用状态和摘要间隔。 |
| `/enable_group <chat_id> <minutes>` | 启用已知群组的定时摘要。 |
| `/disable_group <chat_id>` | 禁用某个群组的定时摘要。 |
| `/set_interval <chat_id> <minutes>` | 更新群组摘要间隔，但不会隐式启用群组。 |
| `/summary` | 手动摘要所有已启用群组。 |
| `/summary <chat_id>` | 手动摘要一个已知群组。 |
| `/reply <user_id> <message>` | 向已知私聊用户发送文本回复。 |

命令菜单 scope 只是可见性辅助。服务端仍会对所有管理员 handler 做 owner 和私聊校验。

## 摘要行为

每个群组都有独立的内部序列游标。

一次摘要任务会：

1. 读取上一次成功游标之后的群消息。
2. 只基于 `message_type` 和 `summary_content` 构建隐私过滤后的 LLM payload。
3. 调用配置的摘要客户端。
4. 将生成的摘要私聊发送给管理员。
5. 只有 Telegram 投递成功且游标未被并发修改时，才推进游标。

LLM 失败、超时、空输出、Telegram 投递失败都会保持游标不变。

定时摘要和手动摘要共用同一个摘要服务和游标逻辑。APScheduler 的 `coalesce` 和 `max_instances=1` 只是本地保护；数据库中的 running-job 约束才是处理重叠任务的正确性边界。

## 私聊中转行为

当非管理员私聊用户向 bot 发送消息时：

1. 原始 update 会被保存。
2. 私聊用户和私聊消息元数据会被保存。
3. 管理员会收到一张信息卡。
4. 如果可行，原始消息会通过 Telegram `copyMessage` 复制给管理员。
5. 成功生成的管理员侧消息 ID 会映射回私聊用户。

如果复制失败，bot 会记录失败并通知管理员。它不会下载或重新上传受保护的 Telegram 内容。

管理员回复只通过回复映射路由。没有上下文的普通管理员消息会被拒绝，而不是基于最近消息猜测目标。

## 保留策略

`RAW_UPDATE_RETENTION_DAYS` 默认是 30。进程内调度器每天运行一次原始 update 保留清理任务。

清理只会脱敏过期的原始 update JSON payload 正文。它会保留：

- 原始 update 审计/状态字段
- 私聊用户
- 私聊消息
- 回复映射
- 摘要状态
- 摘要任务
- 摘要结果

## 隐私边界

- 原始 Telegram update JSON 属于敏感数据，只在配置的保留窗口内保存。
- 服务会保存媒体元数据和 Telegram file identifier，但不会保存媒体文件正文。
- 私聊中转内容不会发送给 LLM。
- 摘要 LLM payload 只由白名单字段构建：消息类型和摘要内容。
- Bot token 和 LLM API key 在数据库中加密存储，WebUI API 永不返回明文。
- 普通日志和审计记录不得包含 bot token、数据库密码、`SETTINGS_ENCRYPTION_KEY`、`WEBUI_ADMIN_TOKEN`、LLM API key、原始 update JSON、私聊中转内容、Telegram 数字 ID、file ID、完整 prompt 正文或原始 provider 响应。
- 配置渲染会脱敏 secret 和敏感数字标识。

## 手动验证清单

使用测试 bot 和非生产数据。

1. 管理员私聊发送 `/start`，确认收到响应。
2. 在群组发送一条测试消息，然后私聊运行 `/groups`，确认群组被发现但处于禁用状态。
3. 使用 `/enable_group <chat_id> <minutes>` 启用一个群组。
4. 发送群组消息，并私聊运行 `/summary <chat_id>`。
5. 确认管理员收到摘要。
6. 让一个非管理员私聊用户向 bot 发消息。
7. 确认管理员收到信息卡和复制消息。
8. 管理员回复映射到的消息，确认私聊用户收到回复。
9. 对已知私聊用户测试 `/reply <user_id> <message>`。
10. 确认没有上下文的普通管理员消息会被拒绝。

## 故障排查

| 现象 | 检查项 |
| --- | --- |
| 没有 polling update | 确认没有 active webhook，并且同一个 bot token 只有一个 polling 进程。 |
| 群消息没有被采集 | 检查 BotFather privacy mode，以及修改后是否重新把 bot 加入群组。 |
| `/groups` 看不到群组 | bot 加入群组并具备接收 update 能力后，在该群组发送一条新消息。 |
| 摘要失败但游标没有推进 | 查看 `summary_jobs.error_type` 和 `summary_jobs.error_message`；失败时保留游标是预期行为。 |
| 管理员收不到摘要或中转通知 | 确认管理员已私聊启动 bot，且没有屏蔽 bot。 |
| 回复被拒绝为 unmapped | 直接回复信息卡或复制消息，等待映射短暂持久化，或对已知用户使用 `/reply`。 |

## 范围边界

v1 暂不包含：

- 多管理员、角色或租户边界
- Webhook 投递
- Redis 队列或水平 worker
- 独立前端服务、Nginx 或 HTTPS 生产方案
- OCR、图像分析、语音转写等媒体理解能力
- 下载或保存 Telegram 媒体文件正文
- 当前聊天回复模式
- 群内公开发布摘要
- 查看 secret 明文或密钥轮换
