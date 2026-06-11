import { useEffect, useMemo, useState } from "react";
import { Empty, Skeleton } from "../ui/semi";
import {
  IconAlertCircle,
  IconArrowUpRight,
  IconCheckCircleStroked,
  IconChevronRight,
  IconGift,
  IconKey,
  IconLineChartStroked,
  IconPieChart2Stroked,
  IconPlay,
  IconPulse,
  IconRefresh,
  IconServer,
  IconSetting,
  IconUserGroup,
  IconUserSetting
} from "@douyinfe/semi-icons";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { DashboardResponse, GroupListItem, RecentAuditLog } from "../api/types";
import { RestartBanner } from "../components/RestartBanner";
import { formatDateTime } from "../utils/format";

type Tone = "blue" | "violet" | "teal" | "orange" | "green" | "red" | "neutral";

interface TrendPoint {
  x: number;
  y: number;
  value: number;
}

interface ActivityItem {
  id: string;
  icon: ReactNode;
  tone: Tone;
  text: ReactNode;
  time: string;
}

function statusLabel(status: string | null | undefined) {
  const labels: Record<string, string> = {
    valid: "已验证",
    invalid: "无效",
    error: "异常",
    unvalidated: "未验证",
    running: "运行中",
    pending: "等待中",
    succeeded: "成功",
    failed: "失败",
    blocked: "已阻塞"
  };
  return labels[status || ""] || status || "未知";
}

function shortDateLabel(daysAgo: number) {
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);
  return `${String(date.getMonth() + 1).padStart(2, "0")}/${String(date.getDate()).padStart(2, "0")}`;
}

function buildTrend(total: number, failed: number) {
  const safeTotal = Math.max(total, 1);
  const succeeded = Math.max(safeTotal - failed, 1);
  const successValues = [0.58, 0.68, 0.56, 0.82, 1, 0.74, 0.88].map((ratio, index) => {
    const value = Math.round(succeeded * ratio);
    return index === 6 ? succeeded : Math.max(value, 1);
  });
  const failedValues = [0.25, 0.2, 0.28, 0.18, 0.3, 0.22, 1].map((ratio, index) => {
    const value = Math.round(Math.max(failed, 1) * ratio);
    return index === 6 ? failed : value;
  });
  const maxValue = Math.max(...successValues, 1);
  const toPoints = (values: number[], floor: number): TrendPoint[] =>
    values.map((value, index) => ({
      x: (640 / 6) * index,
      y: floor - (value / maxValue) * 132,
      value
    }));
  const successPoints = toPoints(successValues, 176);
  const failedPoints = toPoints(failedValues, 190);
  const line = successPoints.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const failedLine = failedPoints.map((point) => `${point.x.toFixed(1)},${point.y.toFixed(1)}`).join(" ");
  const area = `${successPoints[0].x.toFixed(1)},188 ${line} ${successPoints[
    successPoints.length - 1
  ].x.toFixed(1)},188`;
  return { successPoints, line, failedLine, area };
}

function groupTitle(group: GroupListItem) {
  return group.title || group.username || String(group.chat_id);
}

function derivedGroupScore(group: GroupListItem, index: number) {
  if (!group.settings.enabled) {
    return 0;
  }
  const interval = Math.max(group.settings.interval_minutes, 1);
  const daily = Math.max(1, Math.round(1440 / interval));
  const statusPenalty = group.last_summary?.status === "failed" ? -1 : 0;
  return Math.max(1, daily * 7 + Math.max(0, 4 - index) + statusPenalty);
}

function activityMeta(item: RecentAuditLog): { icon: ReactNode; tone: Tone } {
  const entity = item.entity_type.toLowerCase();
  const action = item.action.toLowerCase();
  if (action.includes("delete") || action.includes("fail")) {
    return { icon: <IconAlertCircle />, tone: "red" };
  }
  if (entity.includes("bot") || action.includes("token") || action.includes("secret")) {
    return { icon: <IconKey />, tone: "orange" };
  }
  if (entity.includes("profile") || entity.includes("provider")) {
    return { icon: <IconPulse />, tone: "violet" };
  }
  if (entity.includes("group")) {
    return { icon: <IconUserSetting />, tone: "blue" };
  }
  return { icon: <IconSetting />, tone: "green" };
}

function buildActivityItems(data: DashboardResponse): ActivityItem[] {
  if (data.recent_audit_logs.length > 0) {
    return data.recent_audit_logs.slice(0, 5).map((item) => {
      const meta = activityMeta(item);
      return {
        id: String(item.id),
        icon: meta.icon,
        tone: meta.tone,
        text: (
          <>
            <b>{item.actor}</b> {item.action} <code>{item.entity_type}</code>
            {item.entity_id && <span className="muted-text"> #{item.entity_id}</span>}
          </>
        ),
        time: formatDateTime(item.created_at)
      };
    });
  }

  const fallback: ActivityItem[] = [
    {
      id: "bot-status",
      icon: <IconCheckCircleStroked />,
      tone: data.bot?.status === "valid" ? "green" : "orange",
      text: (
        <>
          Bot <b>{data.bot?.name || "未配置"}</b> 当前状态为 <b>{statusLabel(data.bot?.status)}</b>
        </>
      ),
      time: data.bot?.last_validated_at ? formatDateTime(data.bot.last_validated_at) : "暂无验证时间"
    },
    {
      id: "profile-status",
      icon: <IconPulse />,
      tone: data.default_profile?.enabled ? "violet" : "neutral",
      text: (
        <>
          默认 Summary Profile 为 <b>{data.default_profile?.name || "未配置"}</b>
        </>
      ),
      time: data.default_profile ? data.default_profile.prompt_version : "等待配置"
    },
    {
      id: "groups-status",
      icon: <IconUserGroup />,
      tone: "blue",
      text: (
        <>
          当前 <b>{data.groups.enabled}</b> 个群组启用摘要，共发现 <b>{data.groups.total}</b> 个群组
        </>
      ),
      time: "来自群组配置"
    }
  ];
  return fallback;
}

export function Dashboard() {
  const [data, setData] = useState<DashboardResponse | null>(null);
  const [groups, setGroups] = useState<GroupListItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    try {
      const [dashboardResponse, groupResponse] = await Promise.all([
        api.dashboard(),
        api.groups
          .list({ limit: 5 })
          .then((response) => response.items)
          .catch(() => [])
      ]);
      setData(dashboardResponse);
      setGroups(groupResponse);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const successRate =
    data && data.summary_24h.total > 0
      ? Math.round((data.summary_24h.succeeded / data.summary_24h.total) * 100)
      : 0;

  const trend = useMemo(
    () => buildTrend(data?.summary_24h.total || 0, data?.summary_24h.failed || 0),
    [data?.summary_24h.failed, data?.summary_24h.total]
  );

  const rankedGroups = useMemo(() => {
    if (groups.length > 0) {
      return groups
        .map((group, index) => ({
          id: String(group.id),
          name: groupTitle(group),
          sub: `${group.effective_profile?.name || "默认 Profile"} · ${
            group.settings.enabled ? `${group.settings.interval_minutes}min` : "未启用"
          }`,
          score: derivedGroupScore(group, index),
          status: group.last_summary?.status || (group.settings.enabled ? "running" : "blocked")
        }))
        .sort((left, right) => right.score - left.score)
        .slice(0, 5);
    }
    if (!data) {
      return [];
    }
    return [
      {
        id: "enabled",
        name: "已启用群组",
        sub: "当前启用定时摘要",
        score: data.groups.enabled,
        status: "running"
      },
      {
        id: "discovered",
        name: "已发现群组",
        sub: "Bot 已入库群组",
        score: data.groups.total,
        status: "succeeded"
      },
      {
        id: "pending-profile",
        name: "待绑定 Profile",
        sub: data.default_profile ? "默认 Profile 可回退使用" : "建议先配置默认 Profile",
        score: Math.max(data.groups.total - data.groups.enabled, 0),
        status: data.default_profile ? "pending" : "blocked"
      }
    ];
  }, [data, groups]);

  if (loading && data === null) {
    return <Skeleton active placeholder={<Skeleton.Paragraph rows={12} />} />;
  }

  if (data === null) {
    return <Empty description="Dashboard 暂不可用" />;
  }

  const failedGroups = groups.filter((group) => group.last_summary?.status === "failed").length;
  const distributionTotal = Math.max(data.groups.total, groups.length, 1);
  const enabledHealthy = Math.max(data.groups.enabled - failedGroups, 0);
  const discoveredOnly = Math.max(distributionTotal - enabledHealthy - failedGroups, 0);
  const distribution = [
    { label: "已启用摘要", value: enabledHealthy, tone: "violet", color: "#6366f1" },
    { label: "已发现未启用", value: discoveredOnly, tone: "blue", color: "#3b6ef5" },
    { label: "摘要异常", value: failedGroups, tone: "orange", color: "#e08a1e" }
  ].filter((item) => item.value > 0);
  let donutCursor = 25;
  const donutSegments = distribution.map((item) => {
    const percent = Math.max(0, Math.round((item.value / distributionTotal) * 100));
    const segment = { ...item, percent, offset: donutCursor };
    donutCursor -= percent;
    return segment;
  });
  const activities = buildActivityItems(data);

  return (
    <div className="page dashboard-page">
      <section className="dashboard-welcome">
        <div className="welcome-avatar">SR</div>
        <div className="welcome-text">
          <h1>欢迎回来，admin</h1>
          <p>
            Bot {statusLabel(data.bot?.status || data.telegram_startup.status)}，{data.groups.enabled} 个群组正在产出摘要。
          </p>
        </div>
        <div className="welcome-actions">
          <button className="btn" type="button" onClick={load}>
            <IconRefresh />
            刷新状态
          </button>
          <Link className="btn btn-primary" to="/groups">
            <IconPlay />
            手动触发摘要
          </Link>
        </div>
      </section>

      <RestartBanner items={data.restart_pending} />

      <section className="metric-grid">
        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon blue">
              <IconServer />
            </div>
            <div className="metric-label">Bot 运行状态</div>
          </div>
          <div className="metric-main">
            <div className="metric-value text-value">{data.bot?.name || "未配置"}</div>
            <span className={`status-pill ${data.bot?.status === "valid" ? "green" : "orange"}`}>
              {statusLabel(data.bot?.status || data.telegram_startup.status)}
            </span>
          </div>
          <div className="metric-foot">
            <span className={`status-dot ${data.bot?.status === "valid" ? "green" : "orange"}`} />
            {data.bot?.last_validated_at
              ? `最近验证 ${formatDateTime(data.bot.last_validated_at)}`
              : data.telegram_startup.detail || "等待 Bot 配置"}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon violet">
              <IconUserGroup />
            </div>
            <div className="metric-label">启用群组</div>
          </div>
          <div className="metric-main">
            <div className="metric-value">
              {data.groups.enabled}
              <span className="unit">/ {data.groups.total}</span>
            </div>
            <div className="metric-trend up">
              <IconArrowUpRight />
              {data.groups.total > 0 ? `${Math.round((data.groups.enabled / data.groups.total) * 100)}%` : "0%"}
            </div>
          </div>
          <div className="metric-foot">已发现群组中启用定时摘要的数量</div>
        </div>

        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon teal">
              <IconPulse />
            </div>
            <div className="metric-label">默认 Profile</div>
          </div>
          <div className="metric-main">
            <div className="metric-value text-value">{data.default_profile?.name || "未配置"}</div>
            <span className={`status-pill ${data.default_profile?.enabled ? "green" : "neutral"}`}>
              {data.default_profile?.enabled ? "已启用" : "待配置"}
            </span>
          </div>
          <div className="metric-foot">
            {data.default_profile
              ? `${data.default_profile.prompt_version} · 新群组可默认回退`
              : "请先创建默认 Summary Profile"}
          </div>
        </div>

        <div className="metric-card">
          <div className="metric-top">
            <div className="metric-icon orange">
              <IconRefresh />
            </div>
            <div className="metric-label">近 24h 摘要</div>
          </div>
          <div className="metric-main">
            <div className="metric-value">{data.summary_24h.total}</div>
            <div className={`metric-trend ${data.summary_24h.failed > 0 ? "flat" : "up"}`}>
              {successRate}% 成功率
            </div>
          </div>
          <div className="metric-foot">
            成功 {data.summary_24h.succeeded} · 失败 {data.summary_24h.failed}
          </div>
        </div>
      </section>

      <section className="dashboard-row cols-2-1">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>摘要产出趋势</h2>
              <p>最近 7 天，基于 24h 摘要量稳定派生</p>
            </div>
            <span className="panel-icon">
              <IconLineChartStroked />
            </span>
          </div>
          <div className="panel-body">
            <svg className="dashboard-chart" viewBox="0 0 640 220" preserveAspectRatio="none" role="img">
              <defs>
                <linearGradient id="summaryTrendFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#6366f1" stopOpacity="0.22" />
                  <stop offset="100%" stopColor="#6366f1" stopOpacity="0" />
                </linearGradient>
              </defs>
              <g stroke="#eef0f3" strokeWidth="1">
                <line x1="0" y1="44" x2="640" y2="44" />
                <line x1="0" y1="88" x2="640" y2="88" />
                <line x1="0" y1="132" x2="640" y2="132" />
                <line x1="0" y1="176" x2="640" y2="176" />
              </g>
              <polygon points={trend.area} fill="url(#summaryTrendFill)" />
              <polyline points={trend.line} fill="none" stroke="#6366f1" strokeWidth="3" strokeLinecap="round" />
              <polyline
                points={trend.failedLine}
                fill="none"
                stroke="#e08a1e"
                strokeWidth="2"
                strokeDasharray="5 6"
                strokeLinecap="round"
              />
              {trend.successPoints.map((point, index) => (
                <circle
                  key={`${point.x}-${index}`}
                  cx={point.x}
                  cy={point.y}
                  r={index === trend.successPoints.length - 1 ? 5 : 3.5}
                  fill="#fff"
                  stroke="#6366f1"
                  strokeWidth="2"
                />
              ))}
            </svg>
            <div className="chart-axis">
              {[6, 5, 4, 3, 2, 1, 0].map((daysAgo) => (
                <span key={daysAgo}>{shortDateLabel(daysAgo)}</span>
              ))}
            </div>
            <div className="chart-legend">
              <span>
                <i style={{ background: "#6366f1" }} />
                成功摘要
              </span>
              <span>
                <i style={{ background: "#e08a1e" }} />
                失败摘要
              </span>
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>群组状态分布</h2>
              <p>共 {data.groups.total} 个群组</p>
            </div>
            <span className="panel-icon">
              <IconPieChart2Stroked />
            </span>
          </div>
          <div className="panel-body">
            <div className="donut-wrap">
              <svg className="donut" viewBox="0 0 42 42" role="img">
                <circle cx="21" cy="21" r="15.9155" fill="none" stroke="#eef0f3" strokeWidth="6" />
                {donutSegments.map((segment) => (
                  <circle
                    key={segment.label}
                    cx="21"
                    cy="21"
                    r="15.9155"
                    fill="none"
                    stroke={segment.color}
                    strokeWidth="6"
                    strokeDasharray={`${segment.percent} ${100 - segment.percent}`}
                    strokeDashoffset={segment.offset}
                    strokeLinecap="round"
                  />
                ))}
                <text className="donut-center" x="21" y="20" textAnchor="middle" dominantBaseline="middle">
                  {distributionTotal}
                </text>
                <text className="donut-center-sub" x="21" y="26.5" textAnchor="middle">
                  群组
                </text>
              </svg>
              <div className="donut-legend">
                {donutSegments.map((segment) => (
                  <div className="donut-row" key={segment.label}>
                    <span className={`legend-dot ${segment.tone}`} />
                    <span className="donut-name">{segment.label}</span>
                    <span className="donut-val">{segment.value}</span>
                    <span className="donut-pct">{segment.percent}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="dashboard-row cols-1-1">
        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>群组摘要排行</h2>
              <p>{groups.length > 0 ? "按配置频率估算近 7 天产出" : "使用 Dashboard 汇总数据降级展示"}</p>
            </div>
            <Link className="panel-link" to="/groups">
              查看全部
              <IconChevronRight />
            </Link>
          </div>
          <div className="panel-body">
            <div className="rank-list">
              {rankedGroups.map((group, index) => (
                <div className="rank-row" key={group.id}>
                  <div className={`rank-no ${index < 3 ? "top" : ""}`}>{index + 1}</div>
                  <div className="rank-main">
                    <div className="rank-name">{group.name}</div>
                    <div className="rank-sub">{group.sub}</div>
                  </div>
                  <div className="rank-side">
                    <div className="rank-num">{group.score}</div>
                    <div className="rank-sub">{groups.length > 0 ? "预计摘要" : "项"}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="panel">
          <div className="panel-head">
            <div>
              <h2>最近配置变更</h2>
              <p>审计流</p>
            </div>
            <Link className="panel-link" to="/audit-logs">
              查看全部
              <IconChevronRight />
            </Link>
          </div>
          <div className="panel-body">
            <div className="activity-list">
              {activities.map((item) => (
                <div className="activity-row" key={item.id}>
                  <div className={`activity-icon ${item.tone}`}>{item.icon}</div>
                  <div className="activity-main">
                    <div className="activity-text">{item.text}</div>
                    <div className="activity-time">{item.time}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      <section className="cta-band">
        <div className="cta-copy">
          <h2>让新群组自动进入摘要流程</h2>
          <p>先确认默认 Summary Profile，再为高价值群组打开定时摘要；配置完成后可从审计流追踪每次变更。</p>
        </div>
        <div className="cta-actions">
          <Link className="btn btn-primary" to="/engine">
            <IconPulse />
            配置摘要引擎
          </Link>
          <Link className="btn" to="/groups">
            <IconUserGroup />
            管理群组
          </Link>
          <Link className="btn" to="/audit-logs">
            <IconGift />
            查看审计
          </Link>
        </div>
      </section>
    </div>
  );
}
