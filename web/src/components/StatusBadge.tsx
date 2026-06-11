import { Tag } from "../ui/semi";

const statusLabel: Record<string, string> = {
  valid: "有效",
  invalid: "无效",
  error: "错误",
  unvalidated: "未验证",
  pending: "等待中",
  running: "运行中",
  succeeded: "成功",
  failed: "失败",
  blocked: "已阻塞"
};

const statusColor: Record<string, "green" | "red" | "orange" | "grey" | "blue"> = {
  valid: "green",
  succeeded: "green",
  invalid: "red",
  failed: "red",
  error: "red",
  blocked: "orange",
  running: "blue",
  pending: "blue",
  unvalidated: "grey"
};

export function StatusBadge({ status }: { status: string | null | undefined }) {
  const normalized = status || "unknown";
  return (
    <Tag color={statusColor[normalized] || "grey"} shape="circle">
      <span className={`status-dot status-dot-${statusColor[normalized] || "grey"}`} />
      {statusLabel[normalized] || normalized}
    </Tag>
  );
}
