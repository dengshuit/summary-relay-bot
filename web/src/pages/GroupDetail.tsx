import { useEffect, useMemo, useState } from "react";
import { Button, Empty, InputNumber, Select, Skeleton, Switch, Toast, Typography } from "../ui/semi";
import {
  IconArrowLeft,
  IconListView,
  IconPulse,
  IconRefresh,
  IconSave,
  IconSetting,
  IconUserGroup
} from "@douyinfe/semi-icons";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import type { GroupDetail as GroupDetailType, SummaryJob, SummaryProfile } from "../api/types";
import { JobStatusButton } from "../components/JobStatusButton";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Text } = Typography;

function EnabledStatus({ enabled }: { enabled: boolean }) {
  const tone = enabled ? "green" : "neutral";
  return (
    <span className={`status-pill ${tone}`}>
      <span className={`status-dot status-dot-${tone}`} />
      {enabled ? "已启用" : "未启用"}
    </span>
  );
}

function groupName(group: GroupDetailType) {
  return group.title || group.username || String(group.chat_id);
}

function jobSequence(job: SummaryJob) {
  return `${job.starting_sequence}${job.cutoff_sequence ? `-${job.cutoff_sequence}` : ""}`;
}

function JobCompactRow({ job, active = false }: { job: SummaryJob; active?: boolean }) {
  return (
    <div className={`job-row group-job-row${active ? " active" : ""}`}>
      <StatusBadge status={job.status} />
      <div className="group-job-main">
        <div className="group-job-title">
          {formatDateTime(job.created_at)} · {job.trigger_type}
        </div>
        <div className="group-job-sub">
          {job.model || "-"} · {job.prompt_version || "-"} · 序列 {jobSequence(job)}
        </div>
        {job.result && (
          <div className="group-job-result">
            <span className="status-pill violet">
              <span className="status-dot status-dot-violet" />
              result
            </span>
            <span>
              {job.result.model || "-"} · {job.result.prompt_version} · {job.result.interval_start_sequence}-
              {job.result.interval_end_sequence}
            </span>
          </div>
        )}
        {(job.error_type || job.error_message) && (
          <div className="group-job-error">
            {job.error_type || "summary_failed"} {job.error_message || ""}
          </div>
        )}
      </div>
    </div>
  );
}

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
    return (
      <div className="panel panel-loading">
        <div className="panel-body">
          <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />
        </div>
      </div>
    );
  }

  if (group === null) {
    return (
      <div className="panel empty-panel">
        <div className="panel-body">
          <Empty description="群组不存在" />
        </div>
      </div>
    );
  }

  const activeRunning = group.active_job?.status === "running" || group.active_job?.status === "pending";

  return (
    <div className="page group-detail-page">
      <Button component={Link} to="/groups" theme="borderless" icon={<IconArrowLeft />} className="back-link-button">
        返回群组列表
      </Button>

      <div className="object-head group-detail-head">
        <div className="object-icon">
          <IconUserGroup />
        </div>
        <div className="object-copy">
          <div className="object-title-row">
            <h1>{groupName(group)}</h1>
            <EnabledStatus enabled={group.settings.enabled} />
          </div>
          <div className="object-sub">
            {group.chat_type} · chat_id {group.chat_id} · 发现于 {formatDateTime(group.discovered_at)}
          </div>
        </div>
        <div className="object-actions">
          <Button icon={<IconRefresh />} onClick={load} className="page-refresh-button">
            刷新
          </Button>
          <JobStatusButton groupId={group.id} disabled={activeRunning} onFinished={load} />
        </div>
      </div>

      {activeRunning && <div className="inline-warning">该群有摘要正在生成，暂不能重复触发。</div>}

      <div className="detail-grid group-detail-grid">
        <div className="side-stack">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>摘要设置</h2>
                <p>配置定时摘要、时区和绑定的 Summary Profile。</p>
              </div>
              <span className="panel-icon">
                <IconSetting />
              </span>
            </div>
            <div className="panel-body form-stack form-stack-compact group-settings-form">
              <div className="switch-row settings-switch-row">
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
              <div className="form-actions">
                <Button theme="solid" type="primary" icon={<IconSave />} loading={saving} onClick={save}>
                  保存设置
                </Button>
              </div>
            </div>
          </section>

          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>最近任务</h2>
                <p>最近摘要生成记录、序列范围和结果信息。</p>
              </div>
              <span className="panel-icon">
                <IconListView />
              </span>
            </div>
            <div className="panel-body">
              {group.recent_jobs.length === 0 ? (
                <Empty description="暂无摘要历史" />
              ) : (
                <div className="job-list group-job-list">
                  {group.recent_jobs.map((job) => (
                    <JobCompactRow job={job} key={job.id} />
                  ))}
                </div>
              )}
            </div>
          </section>
        </div>

        <div className="side-stack">
          <section className="panel">
            <div className="panel-head">
              <div>
                <h2>当前状态</h2>
                <p>摘要配置与最近一次摘要游标。</p>
              </div>
              <span className="panel-icon">
                <IconPulse />
              </span>
            </div>
            <div className="panel-body">
              <div className="kv-list group-status-list">
                <div className="kv-row">
                  <span className="k">摘要开关</span>
                  <span className="v">
                    <EnabledStatus enabled={group.settings.enabled} />
                  </span>
                </div>
                <div className="kv-row">
                  <span className="k">间隔</span>
                  <span className="v">{group.settings.interval_minutes} 分钟</span>
                </div>
                <div className="kv-row">
                  <span className="k">timezone</span>
                  <span className="v">{group.settings.timezone}</span>
                </div>
                <div className="kv-row">
                  <span className="k">生效 Profile</span>
                  <span className="v">{group.effective_profile?.name || "默认 Profile"}</span>
                </div>
                <div className="kv-row">
                  <span className="k">最近摘要</span>
                  <span className="v">
                    {group.last_summary ? <StatusBadge status={group.last_summary.status} /> : "-"}
                  </span>
                </div>
                <div className="kv-row">
                  <span className="k">最近摘要序列</span>
                  <span className="v">{group.summary_state?.last_summary_sequence ?? 0}</span>
                </div>
                <div className="kv-row">
                  <span className="k">最近摘要时间</span>
                  <span className="v">{formatDateTime(group.summary_state?.last_summary_at)}</span>
                </div>
              </div>
            </div>
          </section>

          <section className="panel active-job-panel">
            <div className="panel-head">
              <div>
                <h2>活跃任务</h2>
                <p>同一群组已有运行中任务时，手动触发会被限制。</p>
              </div>
              <span className="panel-icon">
                <IconPulse />
              </span>
            </div>
            <div className="panel-body">
              {group.active_job ? (
                <JobCompactRow job={group.active_job} active />
              ) : (
                <div className="quiet-state">
                  <span className="status-pill neutral">
                    <span className="status-dot status-dot-neutral" />
                    当前无运行任务
                  </span>
                </div>
              )}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}
