import { Layout, Nav, Button, Typography, Avatar, Toast } from "../ui/semi";
import { IconMenu, IconRefresh, IconExit, IconComment } from "@douyinfe/semi-icons";
import { useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { clearStoredToken } from "../api/client";
import { navItems } from "../app/routes";

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);

  const selectedKeys = useMemo(() => {
    const matched = navItems.find((item) => {
      if (item.path === "/") {
        return location.pathname === "/";
      }
      return location.pathname.startsWith(item.path);
    });
    return [matched?.path || "/"];
  }, [location.pathname]);

  return (
    <Layout className="app-layout">
      <Sider className={`sidebar ${collapsed ? "sidebar-collapsed" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <IconComment />
          </div>
          {!collapsed && (
            <div>
              <div className="brand-title">Summary Relay</div>
              <Text type="tertiary" size="small">
                配置中心
              </Text>
            </div>
          )}
        </div>
        <Nav
          selectedKeys={selectedKeys}
          className="nav"
          items={navItems.map((item) => ({
            itemKey: item.path,
            text: <Link to={item.path}>{item.label}</Link>,
            icon: item.icon
          }))}
          footer={{
            collapseButton: true
          }}
        />
      </Sider>
      <Layout>
        <Header className="topbar">
          <Button
            icon={<IconMenu />}
            theme="borderless"
            aria-label="折叠导航"
            onClick={() => setCollapsed((value) => !value)}
          />
          <div className="topbar-fill" />
          <Button
            icon={<IconRefresh />}
            theme="borderless"
            aria-label="刷新页面"
            onClick={() => window.location.reload()}
          />
          <div className="topbar-user">
            <Avatar size="small" color="indigo">
              SR
            </Avatar>
            <div className="topbar-user-text">
              <Text strong>admin</Text>
              <Text type="tertiary" size="small">
                token 会话
              </Text>
            </div>
          </div>
          <Button
            icon={<IconExit />}
            theme="borderless"
            aria-label="退出登录"
            onClick={() => {
              clearStoredToken();
              Toast.info("已退出登录");
              navigate("/login", { replace: true });
            }}
          />
        </Header>
        <Content className="content">{children}</Content>
      </Layout>
    </Layout>
  );
}
