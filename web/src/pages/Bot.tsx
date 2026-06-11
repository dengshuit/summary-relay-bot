import { useEffect, useMemo, useState } from "react";
import { Button, Input, InputNumber, Modal, Select, Skeleton, Switch, Toast, Typography } from "../ui/semi";
import {
  IconInfoCircle,
  IconKey,
  IconPlus,
  IconPulse,
  IconRefresh,
  IconSave,
  IconServer,
  IconSetting,
  IconTickCircle
} from "@douyinfe/semi-icons";
import { api } from "../api/client";
import type { BotInstance, BotListResponse } from "../api/types";
import { confirmAction } from "../components/ConfirmAction";
import { SecretInput } from "../components/SecretInput";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Text } = Typography;

type BotCreateState = {
  name: string;
  owner_id: number | null;
  bot_token: string;
  enabled: boolean;
};

function botCreateState(enabled: boolean): BotCreateState {
  return {
    name: "",
    owner_id: null,
    bot_token: "",
    enabled
  };
}

function botEnabledLabel(bot: BotInstance) {
  return bot.enabled ? "当前启用的 Bot 实例" : "未启用的 Bot 实例";
}

export function Bot() {
  const [data, setData] = useState<BotListResponse | null>(null);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [name, setName] = useState("");
  const [ownerId, setOwnerId] = useState<number | undefined>();
  const [botToken, setBotToken] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [createState, setCreateState] = useState<BotCreateState>(botCreateState(true));

  const allBots = useMemo(() => {
    if (!data) {
      return [];
    }
    const byId = new Map<number, BotInstance>();
    if (data.active) {
      byId.set(data.active.id, data.active);
    }
    data.items.forEach((item) => byId.set(item.id, item));
    return [...byId.values()];
  }, [data]);

  const selected = useMemo(
    () => allBots.find((item) => item.id === selectedId) || data?.active || allBots[0] || null,
    [allBots, data?.active, selectedId]
  );

  async function load(preferId?: number) {
    setLoading(true);
    try {
      const next = await api.bot.list();
      setData(next);
      const bot = next.active || next.items[0] || null;
      setSelectedId((current) => preferId || current || bot?.id || null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  useEffect(() => {
    if (selected) {
      setName(selected.name);
      setOwnerId(undefined);
      setBotToken("");
    }
  }, [selected?.id]);

  async function save() {
    if (!selected) {
      return;
    }
    const enablingOther = selected.enabled === false;
    if (enablingOther) {
      const confirmed = await confirmAction({
        title: "启用其他 Bot?",
        content: "v1 同一时间只允许一个启用的 Bot。确认后后端会停用当前 enabled Bot。",
        okText: "确认启用"
      });
      if (!confirmed) {
        return;
      }
    }
    setSaving(true);
    try {
      const payload: {
        id: number;
        name?: string;
        owner_id?: number;
        enabled?: boolean;
        bot_token?: string;
      } = { id: selected.id, name, enabled: true };
      if (ownerId !== undefined) {
        payload.owner_id = ownerId;
      }
      if (botToken.trim()) {
        payload.bot_token = botToken;
      }
      await api.bot.update(payload);
      Toast.success("Bot 配置已保存");
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function validate(bot: BotInstance) {
    setTesting(true);
    try {
      await api.bot.validate({
        id: bot.id,
        ...(botToken.trim() ? { bot_token: botToken } : {})
      });
      Toast.success("测试完成");
      await load();
    } finally {
      setTesting(false);
    }
  }

  function openCreateModal() {
    setCreateState(botCreateState(!data?.active));
    setCreateModalOpen(true);
  }

  async function createBot() {
    if (!createState.name.trim()) {
      Toast.warning("请填写 Bot 名称");
      return;
    }
    if (createState.owner_id === null) {
      Toast.warning("请填写 Owner ID");
      return;
    }
    if (!createState.bot_token.trim()) {
      Toast.warning("请填写 Bot Token");
      return;
    }
    setCreating(true);
    try {
      const created = await api.bot.create({
        name: createState.name,
        owner_id: createState.owner_id,
        enabled: createState.enabled,
        bot_token: createState.bot_token
      });
      Toast.success("Bot 实例已创建");
      setCreateModalOpen(false);
      await load(created.id);
    } finally {
      setCreating(false);
    }
  }

  const createBotModal = (
    <Modal
      title="新增 Bot 实例"
      className="compact-modal bot-create-modal"
      visible={createModalOpen}
      onCancel={() => setCreateModalOpen(false)}
      footer={
        <div className="modal-actions">
          <Button onClick={() => setCreateModalOpen(false)}>取消</Button>
          <Button theme="solid" type="primary" icon={<IconSave />} loading={creating} onClick={createBot}>
            创建 Bot
          </Button>
        </div>
      }
    >
      <div className="form-stack form-stack-compact">
        <div className="field-block">
          <Text strong>名称</Text>
          <Input
            value={createState.name}
            placeholder="例如：生产主号"
            onChange={(value) => setCreateState({ ...createState, name: value })}
          />
        </div>
        <div className="field-block">
          <Text strong>Owner ID</Text>
          <InputNumber
            value={createState.owner_id ?? undefined}
            placeholder="管理员 Telegram numeric user ID"
            hideButtons
            onChange={(value) =>
              setCreateState({ ...createState, owner_id: typeof value === "number" ? value : null })
            }
          />
          <Text type="tertiary" size="small">
            创建后响应只返回脱敏 owner id；修改 owner id 需要重启生效。
          </Text>
        </div>
        <div className="field-block secret-input">
          <div className="field-label-row">
            <Text strong>Bot Token</Text>
            <span className="restart-pill">待重启生效</span>
          </div>
          <Input
            mode="password"
            value={createState.bot_token}
            placeholder="从 BotFather 获取的 token"
            autoComplete="new-password"
            onChange={(value) => setCreateState({ ...createState, bot_token: value })}
          />
          <Text type="tertiary" size="small">
            token 会加密存储；WebUI 不会返回或展示明文。
          </Text>
        </div>
        <div className="switch-row">
          <Switch
            checked={createState.enabled}
            onChange={(checked) => setCreateState({ ...createState, enabled: checked })}
          />
          <Text>创建后启用此 Bot</Text>
        </div>
      </div>
    </Modal>
  );

  if (loading && data === null) {
    return <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />;
  }

  if (!selected) {
    return (
      <div className="page bot-empty-page">
        <div className="object-head">
          <div className="object-icon">
            <IconServer />
          </div>
          <div className="object-copy">
            <div className="object-title-row">
              <h1>Bot 配置</h1>
              <span className="status-pill neutral">
                <span className="status-dot status-dot-neutral" />
                未配置
              </span>
            </div>
            <div className="object-sub">通过 WebUI 创建第一个 Bot 实例，配置 token 与 Owner ID。</div>
          </div>
          <div className="object-actions">
            <Button className="page-refresh-button" icon={<IconRefresh />} onClick={() => load()}>
              刷新
            </Button>
            <Button theme="solid" type="primary" icon={<IconPlus />} onClick={openCreateModal}>
              新增 Bot
            </Button>
          </div>
        </div>
        <div className="panel bot-empty-panel">
          <div className="panel-head">
            <div>
              <h2>还没有 Bot 实例</h2>
              <p>数据库已迁移后，Bot token 与 Owner ID 应通过 WebUI 写入数据库运行配置。</p>
            </div>
            <span className="panel-icon">
              <IconPlus />
            </span>
          </div>
          <div className="panel-body bot-empty-body">
            <div className="bot-empty-copy">
              <div className="bot-empty-title">创建后即可继续测试连接</div>
              <div className="bot-empty-sub">
                secret 会加密保存，页面只展示配置状态；启用 Bot 或修改 token/Owner ID 后仍需重启 polling 生效。
              </div>
            </div>
            <Button theme="solid" type="primary" icon={<IconPlus />} onClick={openCreateModal}>
              新增 Bot 实例
            </Button>
          </div>
        </div>
        {createBotModal}
      </div>
    );
  }

  return (
    <div className="page">
      <div className="object-head">
        <div className="object-icon">
          <IconServer />
        </div>
        <div className="object-copy">
          <div className="object-title-row">
            <h1>{selected.name}</h1>
            <StatusBadge status={selected.status} />
          </div>
          <div className="object-sub">
            {botEnabledLabel(selected)} · v1 同一时间只允许一个启用 · secret 只支持替换，不展示明文
          </div>
        </div>
        <div className="object-actions">
          <Button icon={<IconPlus />} onClick={openCreateModal}>
            新增 Bot
          </Button>
          <Button className="page-refresh-button" icon={<IconRefresh />} onClick={() => load()}>
            刷新
          </Button>
          <Button onClick={() => validate(selected)} loading={testing} icon={<IconTickCircle />}>
            测试连接
          </Button>
        </div>
      </div>

      {createBotModal}

      {selected.needs_restart && (
        <div className="restart-banner">
          <div className="restart-banner-icon">
            <IconPulse />
          </div>
          <div className="restart-banner-text">
            该 Bot 有配置变更待重启生效。运行中的 polling 仍使用旧配置，重启服务后生效。
          </div>
        </div>
      )}

      <div className="detail-grid bot-detail-grid">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>基本配置</h2>
              <p>修改 Bot 名称、Owner ID 与 token 替换值。</p>
            </div>
            <span className="panel-icon">
              <IconSetting />
            </span>
          </div>
          <div className="panel-body form-stack form-stack-compact">
            {allBots.length > 1 && (
              <div className="field-block">
                <Text strong>Bot 实例</Text>
                <Select
                  value={selected.id}
                  optionList={allBots.map((item) => ({
                    label: `${item.name}${item.enabled ? " · enabled" : ""}`,
                    value: item.id
                  }))}
                  onChange={(value) => setSelectedId(Number(value))}
                />
                <Text type="tertiary" size="small">
                  保存未启用实例时会先确认并切换 enabled Bot。
                </Text>
              </div>
            )}
            <div className="field-block">
              <Text strong>名称</Text>
              <Input value={name} onChange={setName} />
            </div>
            <div className="field-block">
              <div className="field-label-row">
                <Text strong>Owner ID</Text>
                <span className="restart-pill">待重启生效</span>
              </div>
              <InputNumber
                value={ownerId}
                placeholder={`当前 ${selected.owner_id_redacted}`}
                onChange={(value) => setOwnerId(typeof value === "number" ? value : undefined)}
                hideButtons
              />
              <Text type="tertiary" size="small">
                留空不修改。后端响应只返回脱敏 owner id。
              </Text>
            </div>
            <SecretInput
              label="Bot Token"
              value={botToken}
              secret={selected.secret}
              restart
              onChange={setBotToken}
            />
            <div className="form-actions">
              <Button theme="solid" type="primary" icon={<IconSave />} loading={saving} onClick={save}>
                保存变更
              </Button>
            </div>
          </div>
        </div>

        <div className="side-stack">
          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>运行状态</h2>
                <p>最近一次验证与启用状态。</p>
              </div>
              <span className="panel-icon">
                <IconPulse />
              </span>
            </div>
            <div className="panel-body">
              <div className="status-summary">
                <div>
                  <div className="status-summary-label">验证状态</div>
                  <div className="status-summary-main">
                    <StatusBadge status={selected.status} />
                  </div>
                </div>
                <Button size="small" onClick={() => validate(selected)} loading={testing} icon={<IconTickCircle />}>
                  测试连接
                </Button>
              </div>
              <div className="kv-list">
                <div className="kv-row">
                  <span className="k">enabled</span>
                  <span className="v">
                    <span className={`status-pill ${selected.enabled ? "green" : "neutral"}`}>
                      <span className={`status-dot status-dot-${selected.enabled ? "green" : "neutral"}`} />
                      {selected.enabled ? "已启用" : "未启用"}
                    </span>
                  </span>
                </div>
                <div className="kv-row">
                  <span className="k">最近验证</span>
                  <span className="v">{formatDateTime(selected.last_validated_at)}</span>
                </div>
                <div className="kv-row">
                  <span className="k">Owner ID</span>
                  <span className="v">{selected.owner_id_redacted}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="panel">
            <div className="panel-head">
              <div>
                <h2>Telegram identity</h2>
                <p>getMe 返回的只读身份与 secret 状态。</p>
              </div>
              <span className="panel-icon">
                <IconInfoCircle />
              </span>
            </div>
            <div className="panel-body">
              <div className="kv-list">
                <div className="kv-row">
                  <span className="k">Telegram username</span>
                  <span className="v">{selected.telegram_username || "-"}</span>
                </div>
                <div className="kv-row">
                  <span className="k">Telegram bot id</span>
                  <span className="v">{selected.telegram_bot_id || "-"}</span>
                </div>
                <div className="kv-row">
                  <span className="k">Bot token</span>
                  <span className="v">
                    <span className={`status-pill ${selected.secret.configured ? "green" : "neutral"}`}>
                      <IconKey />
                      {selected.secret.configured ? "已配置" : "未配置"}
                    </span>
                  </span>
                </div>
                <div className="kv-row">
                  <span className="k">最近更新</span>
                  <span className="v">{formatDateTime(selected.secret.updated_at)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
