import { useEffect, useMemo, useState } from "react";
import { Button, Card, Empty, Input, InputNumber, Select, Skeleton, Toast, Typography } from "../ui/semi";
import { IconSave, IconRefresh, IconTickCircle } from "@douyinfe/semi-icons";
import { api } from "../api/client";
import type { BotInstance, BotListResponse } from "../api/types";
import { confirmAction } from "../components/ConfirmAction";
import { SecretInput } from "../components/SecretInput";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Title, Text } = Typography;

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
      <div className="page-head-row">
        <div>
          <Title heading={2}>Bot</Title>
          <Text type="tertiary">管理当前 Telegram Bot 身份。secret 只支持替换，不展示明文。</Text>
        </div>
        <Button icon={<IconRefresh />} onClick={load}>
          刷新
        </Button>
      </div>

      {selected.needs_restart && (
        <div className="inline-warning">该 Bot 有配置变更待重启生效。运行中的 polling 仍使用旧配置。</div>
      )}

      <div className="detail-grid">
        <Card title="基本配置">
          <div className="form-stack">
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
              <Button onClick={() => validate(selected)} loading={testing} icon={<IconTickCircle />}>
                测试连接
              </Button>
            </div>
          </div>
        </Card>

        <Card title="运行状态">
          <div className="kv-list">
            <div className="kv-row">
              <span>enabled</span>
              <span>{selected.enabled ? "已启用" : "未启用"}</span>
            </div>
            <div className="kv-row">
              <span>验证状态</span>
              <StatusBadge status={selected.status} />
            </div>
            <div className="kv-row">
              <span>最近验证</span>
              <span>{formatDateTime(selected.last_validated_at)}</span>
            </div>
            <div className="kv-row">
              <span>Telegram username</span>
              <span>{selected.telegram_username || "-"}</span>
            </div>
            <div className="kv-row">
              <span>Telegram bot id</span>
              <span>{selected.telegram_bot_id || "-"}</span>
            </div>
            <div className="kv-row">
              <span>Owner ID</span>
              <span>{selected.owner_id_redacted}</span>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}
