import { useEffect, useMemo, useState } from "react";
import { Button, Empty, Input, InputNumber, Select, Skeleton, Toast, Typography } from "../ui/semi";
import {
  IconInfoCircle,
  IconKey,
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

  const selected = useMemo(
    () => data?.items.find((item) => item.id === selectedId) || data?.active || data?.items[0] || null,
    [data, selectedId]
  );

  async function load() {
    setLoading(true);
    try {
      const next = await api.bot.list();
      setData(next);
      const bot = next.active || next.items[0] || null;
      setSelectedId((current) => current || bot?.id || null);
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

  if (loading && data === null) {
    return <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />;
  }

  if (!selected) {
    return <Empty description="暂无 Bot 实例。请先通过后端初始化配置。" />;
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
          <Button icon={<IconRefresh />} onClick={load}>
            刷新
          </Button>
          <Button onClick={() => validate(selected)} loading={testing} icon={<IconTickCircle />}>
            测试连接
          </Button>
        </div>
      </div>

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
            {data && data.items.length > 1 && (
              <div className="field-block">
                <Text strong>Bot 实例</Text>
                <Select
                  value={selected.id}
                  optionList={data.items.map((item) => ({
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
