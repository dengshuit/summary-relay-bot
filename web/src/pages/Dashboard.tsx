import { useEffect, useState } from "react";
import { Button, Card, Empty, Skeleton, Typography } from "../ui/semi";
import { IconServer, IconPulse, IconRefresh, IconUserGroup } from "@douyinfe/semi-icons";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DashboardResponse } from "../api/types";
import { RestartBanner } from "../components/RestartBanner";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Title, Text } = Typography;

export function Dashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      setData(await api.dashboard());
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  if (loading && data === null) {
    return <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />;
  }

  if (data === null) {
    return <Empty description="Dashboard 暂不可用" />;
  }

  const successRate =
    data.summary_24h.total > 0
      ? Math.round((data.summary_24h.succeeded / data.summary_24h.total) * 100)
      : 0;

  return (
    <div className="page">
      <div className="page-head-row">
        <div>
          <Title heading={2}>Dashboard</Title>
          <Text type="tertiary">查看当前 Bot、默认 Profile、群组和最近摘要状态。</Text>
        </div>
        <Button icon={<IconRefresh />} onClick={load}>
          刷新状态
        </Button>
      </div>

      <RestartBanner items={data.restart_pending} />

      <div className="metric-grid">
        <Card className="metric-card">
          <div className="metric-icon blue">
            <IconServer />
          </div>
          <Text type="tertiary">Bot 运行 / 验证</Text>
          <Title heading={4}>{data.bot?.name || "未配置"}</Title>
          <StatusBadge status={data.bot?.status || data.telegram_startup.status} />
          <Text type="tertiary" size="small">
            {data.bot?.last_validated_at
              ? `最近验证 ${formatDateTime(data.bot.last_validated_at)}`
              : data.telegram_startup.detail || "没有 enabled bot"}
          </Text>
        </Card>

        <Card className="metric-card">
          <div className="metric-icon violet">
            <IconUserGroup />
          </div>
          <Text type="tertiary">启用群组</Text>
          <Title heading={4}>
            {data.groups.enabled} / {data.groups.total}
          </Title>
          <Link to="/groups">查看群组</Link>
        </Card>

        <Card className="metric-card">
          <div className="metric-icon teal">
            <IconPulse />
          </div>
          <Text type="tertiary">默认 Summary Profile</Text>
          <Title heading={4}>{data.default_profile?.name || "未配置"}</Title>
          <Text type="tertiary" size="small">
            {data.default_profile
              ? `${data.default_profile.prompt_version} · ${data.default_profile.enabled ? "已启用" : "已禁用"}`
              : "请先创建默认 Profile"}
          </Text>
          <Link to="/engine">配置摘要引擎</Link>
        </Card>

        <Card className="metric-card">
          <div className="metric-icon orange">
            <IconRefresh />
          </div>
          <Text type="tertiary">近 24h 摘要</Text>
          <Title heading={4}>{data.summary_24h.total}</Title>
          <Text type="tertiary" size="small">
            成功 {data.summary_24h.succeeded} · 失败 {data.summary_24h.failed} · 成功率 {successRate}%
          </Text>
        </Card>
      </div>

      <div className="dashboard-grid">
        <Card title="快捷入口">
          <div className="quick-actions">
            <Button component={Link} to="/groups" theme="solid" type="primary">
              手动触发摘要
            </Button>
            <Button component={Link} to="/audit-logs">
              查看审计
            </Button>
            <Button component={Link} to="/engine">
              配置 Provider
            </Button>
          </div>
        </Card>
        <Card title="最近配置变更">
          {data.recent_audit_logs.length === 0 ? (
            <Empty description="暂无审计日志" />
          ) : (
            <div className="activity-list">
              {data.recent_audit_logs.map((item) => (
                <div className="activity-item" key={item.id}>
                  <div>
                    <Text strong>{item.actor}</Text>
                    <Text> {item.action} </Text>
                    <Text code>{item.entity_type}</Text>
                  </div>
                  <Text type="tertiary" size="small">
                    {formatDateTime(item.created_at)}
                  </Text>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
