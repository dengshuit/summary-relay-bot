# Telegram 群聊总结与私聊中转 Bot — 开发者简明需求

## 目标

实现一个单管理员使用的 Telegram Bot。第一版使用 Bot API Polling 运行，不要求公网 Webhook。Bot 能加入多个群，静默采集群消息并增量总结，只把总结私聊发给管理员；同时支持普通用户私聊 Bot，由 Bot 将用户消息复制给管理员，管理员再通过 Bot 回复用户。

完整需求文档：`docs/brainstorms/2026-06-03-telegram-summary-relay-bot-requirements.md`

## V1 范围

### 包含

- 使用 Bot API Polling 接收消息，不要求公网入口。
- 只支持一个管理员，通过 `OWNER_ID` 配置。
- 支持同一个 Bot 加入多个群。
- Bot 在群里默认保持静默，不发总结、不主动回复。
- 按群维护独立总结游标，从上次成功总结后继续。
- 管理员可私聊 Bot 手动触发总结。
- 支持按群定时触发总结。
- 总结结果只私聊发给管理员。
- 群聊媒体进入总结时使用占位符。
- 普通用户私聊 Bot 时，消息通过 `copyMessage` 复制给管理员。
- 管理员 reply 信息卡或复制消息后，Bot 将回复转发给对应用户。
- 支持文本备用命令，例如 `/reply <user_id> <message>`。

### 不包含

- 多管理员、角色、团队、多租户。
- Webhook、Redis Queue、水平扩容。
- Web 管理后台。
- 群内或频道内发布总结。
- 图片理解、语音转文字、文件内容解析。
- 下载、归档或保存媒体文件本体。
- 管理员“当前会话模式”，即不支持管理员不 reply 就连续发送给某个用户。

## 核心行为

### 群聊消息

群聊消息用于总结，不要求原样转发。

处理规则：

- 文本消息：保存并作为原文进入总结。
- 图片消息：作为 `[photo]` 进入总结；如果有 caption，保留 caption。
- 语音消息：作为 `[voice]` 进入总结。
- 文件消息：作为 `[document: filename]` 进入总结。
- 视频消息：作为 `[video]` 进入总结。
- 贴纸消息：作为 `[sticker]` 进入总结。

第一版不要下载群聊媒体文件。

### 私聊消息

私聊消息用于客服式中转，必须尽量保留 Telegram 原始消息形态。

普通用户私聊流程：

1. 普通用户私聊 Bot。
2. Bot 保存原始 update 和消息元数据。
3. Bot 给管理员发送一条用户信息卡。
4. Bot 使用 `copyMessage` 将用户原消息复制给管理员。
5. Bot 为信息卡和复制消息都建立回复映射。

管理员回复流程：

1. 管理员 reply 信息卡或被复制的用户消息。
2. Bot 根据 `reply_to_message.message_id` 查找目标用户。
3. 管理员回复文本时，用 `sendMessage` 发给目标用户。
4. 管理员回复图片、语音、文件等媒体时，优先用 `copyMessage` 发给目标用户。
5. 管理员没有 reply 且不是合法命令时，不要猜测目标用户，应提示管理员需要 reply 某条用户消息。

## 安全与权限规则

- 所有管理员命令都必须在服务端校验 `from_user.id == OWNER_ID`。
- Telegram 命令菜单可见性不是安全边界。
- 普通用户私聊 Bot 时，只应看到 `/start`、`/help` 等普通命令，或不展示额外命令。
- 管理员命令菜单应尽量只对 `OWNER_ID` 私聊可见，可使用 Telegram command scope。
- 群聊里默认不展示管理命令。
- 管理员未 reply 的普通消息不能被转发，避免发错人。
- 不要绕过 Telegram 的复制限制；`copyMessage` 失败时记录失败并通知管理员。
- 总结游标只能在“总结生成成功 + 成功发送给管理员”之后更新。

## 存储边界

数据库保存元数据，不保存媒体文件本体。

建议逻辑表：

- `telegram_updates`：保存原始 Telegram Update JSON 和处理状态。
- `groups`：保存群配置和总结间隔。
- `messages`：保存抽取后的群聊/私聊消息元数据，以及用于总结的文本化内容。
- `private_users`：保存私聊过 Bot 的用户。
- `private_messages`：保存私聊中转的 incoming / outgoing 记录。
- `admin_reply_map`：保存管理员侧 message_id 到目标用户的映射。
- `summary_state`：保存每个群的最后成功总结游标。
- `summary_jobs`：保存手动/定时总结任务状态。
- `summary_results`：保存总结结果和发送信息。

媒体消息可保存这些元数据：

- `file_id`
- `file_unique_id`
- `file_name`
- `file_size`
- `mime_type`
- `caption`
- `message_type`

不要把图片、语音、视频、文件的二进制内容存进数据库。

如果未来需要长期保存媒体文件，应放到对象存储或磁盘，数据库只保存引用。

## 总结游标规则

每个群独立维护游标。

流程：

1. 读取该群的 `last_summary_message_id`。
2. 查询 `message_id > last_summary_message_id` 的群消息。
3. 第一版直接把这段消息整体交给 LLM。
4. 生成总结。
5. 将总结私聊发送给管理员。
6. 记录总结结果。
7. 只有发送成功后，才把游标更新到本次最大 message_id。

如果 LLM 调用失败、上下文过长、Telegram 发送失败：

- 标记 summary job 失败；
- 记录错误；
- 通知管理员；
- 不更新游标。

## 建议开发阶段

### Phase 1：基础 Bot 与数据落库

- 启动 polling。
- 读取配置。
- 连接数据库。
- 保存 raw update。
- 初步区分 private / group / supergroup。

### Phase 2：群消息采集

- 保存群信息。
- 保存群消息。
- 生成 `summary_content`。
- 支持文本和媒体占位。

### Phase 3：管理员命令与手动总结

- `/start`
- `/groups`
- `/summary`
- `/summary <chat_id>`
- 调用 LLM 总结。
- 总结私发管理员。
- 安全更新游标。

### Phase 4：定时总结

- 每群配置总结间隔。
- 定时扫描到期群。
- 创建 summary job。
- 复用手动总结逻辑。

### Phase 5：私聊中转

- 普通用户私聊 Bot。
- Bot 发送用户信息卡给管理员。
- Bot 使用 `copyMessage` 复制用户消息给管理员。
- 建立信息卡和复制消息的 reply 映射。

### Phase 6：管理员代回复

- 管理员 reply 信息卡或复制消息。
- Bot 查 `admin_reply_map`。
- 文本用 `sendMessage` 发给用户。
- 媒体用 `copyMessage` 发给用户。
- 未 reply 的普通管理员消息应拒绝并提示。

### Phase 7：命令菜单与错误处理

- 管理员命令 scope。
- 普通用户 help 文案。
- 群聊不展示管理命令。
- copy 失败提示。
- 总结失败提示。
- 用户屏蔽 Bot 时的发送失败提示。

## 推荐技术栈

- Python
- aiogram 3.x
- PostgreSQL
- SQLAlchemy 或 asyncpg
- APScheduler 或类似定时器
- Docker Compose

Redis 第一版可以先不引入。后续如果切 Webhook、多 worker 或需要更强队列能力，再引入 Redis Queue。

## 需要规划阶段再定的事项

- 是否必须 PostgreSQL，还是允许本地 SQLite 起步。
- polling、scheduler、summary worker 是同进程 async task，还是拆成多个进程。
- raw update 保留多久。
- 管理员命令的最终列表和文案。
- 普通用户 `/start`、`/help` 文案。
- LLM provider、model、timeout、retry 策略。
- 总结 prompt 和 `prompt_version` 设计。
