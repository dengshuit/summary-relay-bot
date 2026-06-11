import { useEffect, useState } from "react";
import { Button, Card, Empty, Input, Select, Skeleton, Typography } from "../ui/semi";
import { IconChevronDown, IconListView, IconRefresh, IconSearch } from "@douyinfe/semi-icons";
import { api } from "../api/client";
import type { AuditLog } from "../api/types";
import { compactJson, formatFullDateTime } from "../utils/format";

const { Title, Text } = Typography;

function auditTone(action: string) {
  const normalized = action.toLowerCase();
  if (normalized.includes("delete") || normalized.includes("disable") || normalized.includes("fail")) {
    return "red";
  }
  if (normalized.includes("replace") || normalized.includes("update") || normalized.includes("trigger")) {
    return "orange";
  }
  if (normalized.includes("create") || normalized.includes("set_default")) {
    return "green";
  }
  return "violet";
}

export function AuditLogs() {
  const [items, setItems] = useState<AuditLog[]>([]);
  const [nextCursor, setNextCursor] = useState<string | null>(null);
  const [entityType, setEntityType] = useState("");
  const [action, setAction] = useState("");
  const [from, setFrom] = useState("");
  const [to, setTo] = useState("");
  const [loading, setLoading] = useState(true);

  async function load(cursor?: string | null, append = false) {
    setLoading(true);
    try {
      const response = await api.auditLogs.list({
        entity_type: entityType,
        action,
        from,
        to,
        cursor,
        limit: 50
      });
      setItems((current) => (append ? [...current, ...response.items] : response.items));
      setNextCursor(response.next_cursor);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  return (
    <div className="page audit-page">
      <div className="page-head-row audit-head-row">
        <div>
          <Title heading={2}>审计日志</Title>
          <Text type="tertiary">记录管理面板的重要配置变更，before / after 均由后端脱敏。</Text>
        </div>
        <Button className="page-refresh-button" icon={<IconRefresh />} onClick={() => load()}>
          刷新
        </Button>
      </div>

      <Card className="filter-card compact-filter-card audit-filter-card">
        <div className="filter-bar">
          <Select
            value={entityType}
            optionList={[
              { label: "全部对象", value: "" },
              { label: "bot_instance", value: "bot_instance" },
              { label: "llm_provider", value: "llm_provider" },
              { label: "summary_profile", value: "summary_profile" },
              { label: "group_summary_settings", value: "group_summary_settings" },
              { label: "summary_job", value: "summary_job" }
            ]}
            onChange={(value) => setEntityType(String(value))}
          />
          <Input
            prefix={<IconSearch />}
            value={action}
            placeholder="action"
            onChange={setAction}
            onEnterPress={() => load()}
          />
          <Input type="datetime-local" value={from} onChange={setFrom} />
          <Input type="datetime-local" value={to} onChange={setTo} />
          <Button theme="solid" type="primary" onClick={() => load()}>
            筛选
          </Button>
        </div>
      </Card>

      {loading && items.length === 0 ? (
        <div className="panel panel-loading">
          <div className="panel-body">
            <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />
          </div>
        </div>
      ) : items.length === 0 ? (
        <div className="panel empty-panel">
          <div className="panel-body">
            <Empty description="暂无审计日志" />
          </div>
        </div>
      ) : (
        <section className="panel audit-panel">
          <div className="panel-head">
            <div>
              <h2>操作记录</h2>
              <p>{items.length} 条已加载日志，展开后查看脱敏 before / after。</p>
            </div>
            <span className="panel-icon">
              <IconListView />
            </span>
          </div>
          <div className="panel-body">
            <div className="timeline audit-timeline">
              {items.map((item) => (
                <article className="audit-row audit-activity-row" key={item.id}>
                  <div className={`audit-dot status-dot-${auditTone(item.action)}`} />
                  <div className="audit-main">
                    <div className="audit-line audit-activity-line">
                      <span className="audit-actor">{item.actor}</span>
                      <span className="audit-action">{item.action}</span>
                      <span className="audit-entity">{item.entity_type}</span>
                      {item.entity_id && <span className="audit-entity-id">#{item.entity_id}</span>}
                    </div>
                    <div className="audit-time">{formatFullDateTime(item.created_at)}</div>
                    <details className="audit-diff-details">
                      <summary>
                        <span>查看 before / after</span>
                        <IconChevronDown />
                      </summary>
                      <div className="diff-grid audit-diff-grid">
                        <div>
                          <div className="diff-title">before</div>
                          <pre className="audit-pre">{compactJson(item.redacted_before)}</pre>
                        </div>
                        <div>
                          <div className="diff-title">after</div>
                          <pre className="audit-pre">{compactJson(item.redacted_after)}</pre>
                        </div>
                      </div>
                    </details>
                  </div>
                </article>
              ))}
            </div>
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
