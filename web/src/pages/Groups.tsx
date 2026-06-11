import { useEffect, useMemo, useState } from "react";
import { Button, Card, Empty, Input, Select, Skeleton, Typography } from "../ui/semi";
import { IconRefresh, IconSearch } from "@douyinfe/semi-icons";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import type { GroupListItem, SummaryProfile } from "../api/types";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Title, Text } = Typography;

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
    <div className="page">
      <div className="page-head-row">
        <div>
          <Title heading={2}>群组</Title>
          <Text type="tertiary">群组由 bot 被拉进群后自动发现入库，这里只配置摘要策略。</Text>
        </div>
        <Button icon={<IconRefresh />} onClick={() => load()}>
          刷新
        </Button>
      </div>

      <Card className="filter-card">
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
        <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />
      ) : groups.length === 0 ? (
        <Empty description="把 bot 拉进群组后会自动出现在这里" />
      ) : (
        <Card>
          <div className="table-wrap">
            <table className="data-table">
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
                      <div className="table-title">{group.title || group.username || String(group.chat_id)}</div>
                      <Text type="tertiary" size="small">
                        {group.chat_type} · {group.chat_id} · {formatDateTime(group.discovered_at)}
                      </Text>
                    </td>
                    <td>{group.settings.enabled ? "已启用" : "未启用"}</td>
                    <td>{group.settings.enabled ? `${group.settings.interval_minutes} min` : "-"}</td>
                    <td>{group.effective_profile?.name || "使用默认"}</td>
                    <td>
                      {group.last_summary ? (
                        <div className="last-summary">
                          <StatusBadge status={group.last_summary.status} />
                          <Text type="tertiary" size="small">
                            {formatDateTime(group.last_summary.finished_at)}
                          </Text>
                        </div>
                      ) : (
                        "-"
                      )}
                    </td>
                    <td>
                      <Button component={Link} to={`/groups/${group.id}`} size="small">
                        详情
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
        </Card>
      )}
    </div>
  );
}
