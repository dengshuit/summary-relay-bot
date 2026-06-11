import { useEffect, useMemo, useState } from "react";
import { Button, Card, Empty, Input, Select, Skeleton, Typography } from "../ui/semi";
import { IconChevronRight, IconRefresh, IconSearch, IconUserGroup } from "@douyinfe/semi-icons";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { GroupListItem, SummaryProfile } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Title, Text } = Typography;

function EnabledStatus({ enabled }: { enabled: boolean }) {
  const tone = enabled ? "green" : "neutral";
  return (
    <span className={`status-pill ${tone}`}>
      <span className={`status-dot status-dot-${tone}`} />
      {enabled ? "已启用" : "未启用"}
    </span>
  );
}

function groupName(group: GroupListItem) {
  return group.title || group.username || String(group.chat_id);
}

export function Groups() {
  const [groups, setGroups] = useState<GroupListItem[]>([]);
  const [profiles, setProfiles] = useState<SummaryProfile[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [enabled, setEnabled] = useState<boolean | null>(null);
  const [profileId, setProfileId] = useState<number | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const profileOptions = useMemo(
    () => [
      { label: "全部 Profile", value: "" },
      ...profiles.map((profile) => ({ label: profile.name, value: String(profile.id) }))
    ],
    [profiles]
  );

  async function load(cursor?: string | null, append = false) {
    setLoading(true);
    try {
      const [groupResponse, profileResponse] = await Promise.all([
        api.groups.list({
          q,
          enabled,
          profile_id: profileId,
          status,
          cursor,
          limit: 50
        }),
        api.profiles.list()
      ]);
      setGroups((current) => (append ? [...current, ...groupResponse.items] : groupResponse.items));
      setNextCursor(groupResponse.next_cursor);
      setProfiles(profileResponse.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="page groups-page">
      <div className="page-head-row groups-head-row">
        <div>
          <Title heading={2}>群组</Title>
          <Text type="tertiary">群组由 bot 被拉进群后自动发现入库，这里只配置摘要策略。</Text>
        </div>
        <Button className="page-refresh-button" icon={<IconRefresh />} onClick={() => load()}>
          刷新
        </Button>
      </div>

      <Card className="filter-card compact-filter-card groups-filter-card">
        <div className="filter-bar">
          <Input
            prefix={<IconSearch />}
            value={q}
            placeholder="搜索群名"
            onChange={setQ}
            onEnterPress={() => load()}
          />
          <Select
            value={enabled === null ? "" : String(enabled)}
            optionList={[
              { label: "全部状态", value: "" },
              { label: "已启用", value: "true" },
              { label: "未启用", value: "false" }
            ]}
            onChange={(value) => {
              const normalized = String(value);
              setEnabled(normalized === "" ? null : normalized === "true");
            }}
          />
          <Select
            value={profileId === null ? "" : String(profileId)}
            optionList={profileOptions}
            onChange={(value) => setProfileId(String(value) === "" ? null : Number(value))}
          />
          <Select
            value={status || ""}
            optionList={[
              { label: "全部摘要状态", value: "" },
              { label: "成功", value: "succeeded" },
              { label: "失败", value: "failed" },
              { label: "运行中", value: "running" },
              { label: "无摘要", value: "none" }
            ]}
            onChange={(value) => setStatus(String(value) || null)}
          />
          <Button theme="solid" type="primary" onClick={() => load()}>
            筛选
          </Button>
        </div>
      </Card>

      {loading && groups.length === 0 ? (
        <div className="panel panel-loading">
          <div className="panel-body">
            <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />
          </div>
        </div>
      ) : groups.length === 0 ? (
        <div className="panel empty-panel">
          <div className="panel-body">
            <Empty description="把 bot 拉进群组后会自动出现在这里" />
          </div>
        </div>
      ) : (
        <section className="panel groups-table-panel">
          <div className="panel-head">
            <div>
              <h2>群组列表</h2>
              <p>{groups.length} 个已加载群组，点击详情查看摘要配置和任务历史。</p>
            </div>
            <span className="panel-icon">
              <IconUserGroup />
            </span>
          </div>
          <div className="table-wrap groups-table-wrap">
            <table className="data-table groups-table">
              <thead>
                <tr>
                  <th>群名</th>
                  <th>摘要开关</th>
                  <th>间隔</th>
                  <th>绑定 Profile</th>
                  <th>最近摘要</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {groups.map((group) => (
                  <tr key={group.id}>
                    <td>
                      <div className="group-cell-main">
                        <span className="group-avatar">
                          <IconUserGroup />
                        </span>
                        <div className="group-cell-copy">
                          <Link className="table-title group-title-link" to={`/groups/${group.id}`}>
                            {groupName(group)}
                          </Link>
                          <div className="group-chat-meta">
                            <span>{group.chat_type}</span>
                            <span>chat_id {group.chat_id}</span>
                            <span>发现于 {formatDateTime(group.discovered_at)}</span>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>
                      <EnabledStatus enabled={group.settings.enabled} />
                    </td>
                    <td>
                      <span className={group.settings.enabled ? "interval-value" : "muted-text"}>
                        {group.settings.enabled ? `${group.settings.interval_minutes} min` : "-"}
                      </span>
                    </td>
                    <td>
                      <span className="profile-value">{group.effective_profile?.name || "使用默认"}</span>
                    </td>
                    <td>
                      {group.last_summary ? (
                        <div className="last-summary">
                          <StatusBadge status={group.last_summary.status} />
                          <span className="last-summary-time">{formatDateTime(group.last_summary.finished_at)}</span>
                          {group.last_summary.error_type && (
                            <span className="summary-error-type">{group.last_summary.error_type}</span>
                          )}
                        </div>
                      ) : (
                        <span className="status-pill neutral">
                          <span className="status-dot status-dot-neutral" />
                          无摘要
                        </span>
                      )}
                    </td>
                    <td>
                      <Button component={Link} to={`/groups/${group.id}`} size="small" className="row-arrow-button">
                        详情 <IconChevronRight />
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {nextCursor && (
            <div className="load-more">
              <Button loading={loading} onClick={() => load(nextCursor, true)}>
                加载更多
              </Button>
            </div>
          )}
        </section>
      )}
    </div>
  );
}
