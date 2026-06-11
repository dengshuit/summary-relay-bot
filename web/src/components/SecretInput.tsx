import { Input, Typography } from "../ui/semi";
import { IconAlertTriangle, IconKey } from "@douyinfe/semi-icons";
import type { SecretState } from "../api/types";
import { formatDateTime } from "../utils/format";

const { Text } = Typography;

export function SecretInput({
  label,
  value,
  secret,
  onChange,
  restart
}: {
  label: string;
  value: string;
  secret: SecretState;
  onChange: (value: string) => void;
  restart?: boolean;
}) {
  return (
    <div className="field-block secret-input">
      <div className="field-label-row">
        <Text strong>{label}</Text>
        {restart && <span className="restart-pill">待重启生效</span>}
      </div>
      <div className="secret-meta">
        <span className={`status-pill ${secret.configured ? "green" : "neutral"}`}>
          <IconKey />
          {secret.configured ? "已配置" : "未配置"}
        </span>
        <Text type="tertiary" size="small">
          {secret.updated_at ? `最近更新 ${formatDateTime(secret.updated_at)}` : "没有明文可查看"}
        </Text>
      </div>
      <Input
        mode="password"
        value={value}
        placeholder={secret.configured ? "保持留空，不修改当前 secret" : "输入 secret"}
        autoComplete="new-password"
        onChange={onChange}
      />
      {value.trim() && (
        <div className="secret-replace-hint">
          <IconAlertTriangle />
          将替换现有 secret，保存后生效。
        </div>
      )}
      <Text type="tertiary" size="small">
        输入新值 = 替换；留空 = 不修改。页面不会显示明文 secret。
      </Text>
    </div>
  );
}
