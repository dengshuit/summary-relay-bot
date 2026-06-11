import { useEffect, useState } from "react";
import { Button, Card, Collapse, Empty, Input, Select, Skeleton, Typography } from "../ui/semi";
import { IconRefresh, IconSearch } from "@douyinfe/semi-icons";
import { api } from "../api/client";
import type { AuditLog } from "../api/types";
import { compactJson, formatFullDateTime } from "../utils/format";

const { Title, Text } = Typography;

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
    <div className="page">
      <div className="page-head-row">
        <div>
          <Title heading={2}>审计日志</Title>
          <Text type="tertiary">记录管理面板的重要配置变更，before / after 均由后端脱敏。</Text>
        </div>
        <Button icon={<IconRefresh />} onClick={() => load()}>
          刷新
        </Button>
      </div>

      <Card className="filter-card">
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
        <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />
      ) : items.length === 0 ? (
        <Empty description="暂无审计日志" />
      ) : (
        <Card>
          <div className="timeline">
            {items.map((item) => (
              <div className="audit-row" key={item.id}>
                <div className="audit-dot" />
                <div className="audit-main">
                  <div className="audit-line">
                    <Text strong>{item.actor}</Text>
                    <Text> {item.action} </Text>
                    <Text code>{item.entity_type}</Text>
                    {item.entity_id && <Text type="tertiary"> #{item.entity_id}</Text>}
                  </div>
                  <Text type="tertiary" size="small">
                    {formatFullDateTime(item.created_at)}
                  </Text>
                  <Collapse>
                    <Collapse.Panel header="查看 before / after" itemKey="diff">
                      <div className="diff-grid">
                        <div>
                          <Text strong>before</Text>
                          <pre>{compactJson(item.redacted_before)}</pre>
                        </div>
                        <div>
                          <Text strong>after</Text>
                          <pre>{compactJson(item.redacted_after)}</pre>
                        </div>
                      </div>
                    </Collapse.Panel>
                  </Collapse>
                </div>
              </div>
            ))}
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
