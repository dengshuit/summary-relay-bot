import { useEffect, useMemo, useState } from "react";
import { Button, Card, Empty, InputNumber, Select, Skeleton, Switch, Toast, Typography } from "../ui/semi";
import { IconArrowLeft, IconRefresh, IconSave } from "@douyinfe/semi-icons";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { GroupDetail as GroupDetailType, SummaryProfile } from "../api/types";
import { JobStatusButton } from "../components/JobStatusButton";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Title, Text } = Typography;

export function GroupDetail() {
  const { groupId } = useParams();
  const numericGroupId = Number(groupId);
  const [group, setGroup] = useState<GroupDetailType | null>(null);
  const [profiles, setProfiles] = useState<SummaryProfile[]>([]);
  const [enabled, setEnabled] = useState(false);
  const [intervalMinutes, setIntervalMinutes] = useState(300);
  const [summaryProfileId, setSummaryProfileId] = useState<number | null>(null);
  const [timezone, setTimezone] = useState("UTC");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const profileOptions = useMemo(
    () => [
      { label: "不绑定，使用默认 Profile", value: "" },
      ...profiles.map((profile) => ({ label: profile.name, value: String(profile.id) }))
    ],
    [profiles]
  );

  async function load() {
    setLoading(true);
    try {
      const [groupResponse, profileResponse] = await Promise.all([
        api.groups.detail(numericGroupId),
        api.profiles.list()
      ]);
      setGroup(groupResponse);
      setProfiles(profileResponse.items);
      setEnabled(groupResponse.settings.enabled);
      setIntervalMinutes(groupResponse.settings.interval_minutes);
      setSummaryProfileId(groupResponse.settings.summary_profile_id);
      setTimezone(groupResponse.settings.timezone);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (Number.isFinite(numericGroupId)) {
      void load();
    }
  }, [numericGroupId]);

  async function save() {
    setSaving(true);
    try {
      await api.groups.updateSettings(numericGroupId, {
        enabled,
        interval_minutes: intervalMinutes,
        summary_profile_id: summaryProfileId,
        timezone
      });
      Toast.success("群组摘要设置已保存");
      await load();
    } finally {
      setSaving(false);
    }
  }

  if (loading && group === null) {
    return <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />;
  }

  if (group === null) {
    return <Empty description="群组不存在" />;
  }

  const activeRunning = group.active_job?.status === "running" || group.active_job?.status === "pending";

  return (
    <div className="page">
      <Button component={Link} to="/groups" theme="borderless" icon={<IconArrowLeft />}>
        返回群组列表
      </Button>

      <div className="page-head-row">
        <div>
          <Title heading={2}>{group.title || group.username || group.chat_id}</Title>
          <Text type="tertiary">
            {group.chat_type} · chat_id {group.chat_id} · 发现于 {formatDateTime(group.discovered_at)}
          </Text>
        </div>
        <div className="head-actions">
          <Button icon={<IconRefresh />} onClick={load}>
            刷新
          </Button>
          <JobStatusButton groupId={group.id} disabled={activeRunning} onFinished={load} />
        </div>
      </div>

      {activeRunning && <div className="inline-warning">该群有摘要正在生成，暂不能重复触发。</div>}

      <div className="detail-grid">
        <Card title="摘要设置">
          <div className="form-stack">
            <div className="switch-row">
              <Switch checked={enabled} onChange={setEnabled} />
              <Text>启用定时摘要</Text>
            </div>
            <div className="form-grid-2">
              <div className="field-block">
                <Text strong>间隔（分钟）</Text>
                <InputNumber
                  min={1}
                  value={intervalMinutes}
                  onChange={(value) => setIntervalMinutes(typeof value === "number" ? value : 300)}
                />
              </div>
              <div className="field-block">
                <Text strong>timezone</Text>
                <Select
                  value={timezone}
                  optionList={[
                    { label: "UTC", value: "UTC" },
                    { label: "Asia/Shanghai", value: "Asia/Shanghai" },
                    { label: "America/New_York", value: "America/New_York" }
                  ]}
                  onChange={(value) => setTimezone(String(value))}
                />
              </div>
            </div>
            <div className="field-block">
              <Text strong>绑定 Summary Profile</Text>
              <Select
                value={summaryProfileId === null ? "" : String(summaryProfileId)}
                optionList={profileOptions}
                onChange={(value) => setSummaryProfileId(String(value) === "" ? null : Number(value))}
              />
              <Text type="tertiary" size="small">
                不绑定时使用默认 Profile。
              </Text>
            </div>
            <Button theme="solid" type="primary" icon={<IconSave />} loading={saving} onClick={save}>
              保存设置
            </Button>
          </div>
        </Card>

        <Card title="状态概览">
          <div className="kv-list">
            <div className="kv-row">
              <span>摘要开关</span>
              <span>{group.settings.enabled ? "已启用" : "未启用"}</span>
            </div>
            <div className="kv-row">
              <span>间隔</span>
              <span>{group.settings.interval_minutes} 分钟</span>
            </div>
            <div className="kv-row">
              <span>生效 Profile</span>
              <span>{group.effective_profile?.name || "默认 Profile"}</span>
            </div>
            <div className="kv-row">
              <span>最近摘要序列</span>
              <span>{group.summary_state?.last_summary_sequence ?? 0}</span>
            </div>
            <div className="kv-row">
              <span>最近摘要时间</span>
              <span>{formatDateTime(group.summary_state?.last_summary_at)}</span>
            </div>
            <div className="kv-row">
              <span>活跃任务</span>
              <span>{group.active_job ? <StatusBadge status={group.active_job.status} /> : "-"}</span>
            </div>
          </div>
        </Card>
      </div>

      <Card title="最近摘要">
        {group.recent_jobs.length === 0 ? (
          <Empty description="暂无摘要历史" />
        ) : (
          <div className="job-list">
            {group.recent_jobs.map((job) => (
              <div className="job-row" key={job.id}>
                <StatusBadge status={job.status} />
                <div>
                  <Text strong>{formatDateTime(job.created_at)}</Text>
                  <div>
                    <Text type="tertiary" size="small">
                      {job.model || "-"} · {job.prompt_version || "-"} · 序列 {job.starting_sequence}
                      {job.cutoff_sequence ? `-${job.cutoff_sequence}` : ""}
                    </Text>
                  </div>
                  {(job.error_type || job.error_message) && (
                    <Text type="danger" size="small">
                      {job.error_type || "summary_failed"} {job.error_message || ""}
                    </Text>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
