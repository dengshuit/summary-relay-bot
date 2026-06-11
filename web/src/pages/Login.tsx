import { useState } from "react";
import { Button, Card, Input, Toast, Typography } from "../ui/semi";
import { IconKey, IconComment, IconAlertTriangle } from "@douyinfe/semi-icons";
import { useLocation, useNavigate } from "react-router-dom";
import { api, clearStoredToken, setStoredToken } from "../api/client";

const { Title, Text } = Typography;

export function Login() {
  const navigate = useNavigate();
  const location = useLocation();
  const [token, setToken] = useState("");
  const [loading, setLoading] = useState(false);
  const [authFailed, setAuthFailed] = useState(Boolean(location.state?.authFailed));

  async function submit() {
    const trimmed = token.trim();
    if (!trimmed) {
      setAuthFailed(true);
      return;
    }
    setLoading(true);
    setAuthFailed(false);
    setStoredToken(trimmed);
    try {
      await api.dashboard();
      Toast.success("已登录");
      navigate("/", { replace: true });
    } catch {
      clearStoredToken();
      setAuthFailed(true);
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="login-page">
      <Card className="login-card" shadows="always">
        <div className="login-mark">
          <IconComment />
        </div>
        <Title heading={3}>Summary Relay 配置中心</Title>
        <Text type="tertiary">输入管理 token 以继续</Text>
        {authFailed && (
          <div className="auth-error">
            <IconAlertTriangle />
            <span>认证失败</span>
          </div>
        )}
        <div className="login-form">
          <Text strong>管理 Token</Text>
          <Input
            mode="password"
            prefix={<IconKey />}
            value={token}
            placeholder="管理 token"
            autoComplete="off"
            onChange={setToken}
            onEnterPress={submit}
          />
          <Text type="tertiary" size="small">
            token 仅存于 sessionStorage，关闭页面即失效。
          </Text>
          <Button theme="solid" type="primary" loading={loading} onClick={submit}>
            登录
          </Button>
        </div>
        <Text type="tertiary" size="small">
          单 token 认证 · 无用户名密码 · v1 不支持记住我
        </Text>
      </Card>
    </main>
  );
}
