import { Toast } from "../ui/semi";
import {
  IconComment,
  IconExit,
  IconExternalOpen,
  IconGithubLogo,
  IconMenu
} from "@douyinfe/semi-icons";
import { useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api, clearStoredToken } from "../api/client";
import { navItems } from "../app/routes";

const navGroups = [
  { title: "总览", paths: ["/"] },
  { title: "配置", paths: ["/bot", "/engine", "/groups"] },
  { title: "运维", paths: ["/audit-logs"] }
];

function isMobileViewport() {
  return window.matchMedia("(max-width: 860px)").matches;
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [pendingCount, setPendingCount] = useState(0);

  const activeItem = useMemo(() => {
    return (
      navItems.find((item) => {
        if (item.path === "/") {
          return location.pathname === "/";
        }
        return location.pathname === item.path || location.pathname.startsWith(`${item.path}/`);
      }) || navItems[0]
    );
  }, [location.pathname]);

  const itemsByPath = useMemo(() => new Map(navItems.map((item) => [item.path, item])), []);

  useEffect(() => {
    let ignore = false;
    api
      .dashboard()
      .then((response) => {
        if (!ignore) {
          setPendingCount(response.restart_pending.length);
        }
      })
      .catch(() => {
        if (!ignore) {
          setPendingCount(0);
        }
      });
    return () => {
      ignore = true;
    };
  }, []);

  function toggleNavigation() {
    if (isMobileViewport()) {
      setMobileOpen((value) => !value);
      return;
    }
    setCollapsed((value) => !value);
  }

  function logout() {
    clearStoredToken();
    Toast.info("已退出登录");
    navigate("/login", { replace: true });
  }

  return (
    <div className={`app-shell ${collapsed ? "is-collapsed" : ""} ${mobileOpen ? "is-nav-open" : ""}`}>
      <button
        className="shell-scrim"
        type="button"
        aria-label="关闭导航"
        onClick={() => setMobileOpen(false)}
      />

      <aside className="shell-sidebar" aria-label="主导航">
        <div className="shell-brand">
          <div className="shell-brand-mark">
            <IconComment />
          </div>
          <div className="shell-brand-text">
            <div className="shell-brand-name">Summary Relay</div>
            <div className="shell-brand-sub">配置中心</div>
          </div>
        </div>

        <nav className="shell-nav">
          {navGroups.map((group) => (
            <div className="shell-nav-group" key={group.title}>
              <div className="shell-nav-section">{group.title}</div>
              {group.paths.map((path) => {
                const item = itemsByPath.get(path);
                if (!item) {
                  return null;
                }
                const active = activeItem.path === item.path;
                const badge = item.path === "/bot" && pendingCount > 0 ? String(pendingCount) : null;
                return (
                  <Link
                    className={`shell-nav-item ${active ? "is-active" : ""}`}
                    to={item.path}
                    key={item.path}
                    title={collapsed ? item.label : undefined}
                    onClick={() => setMobileOpen(false)}
                  >
                    <span className="shell-nav-icon">{item.icon}</span>
                    <span className="shell-nav-label">{item.label}</span>
                    {badge && <span className="shell-nav-badge">{badge}</span>}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="shell-sidebar-foot">
          <a
            className="shell-project-chip"
            href="https://github.com/dengshuit/summary-relay-bot"
            target="_blank"
            rel="noreferrer"
            title="GitHub 开源项目"
          >
            <IconGithubLogo />
            <span className="shell-project-meta">
              <span className="shell-project-name">GitHub 开源</span>
              <span className="shell-project-sub">summary-relay-bot</span>
            </span>
            <IconExternalOpen className="shell-project-ext" />
          </a>
        </div>
      </aside>

      <div className="shell-main">
        <header className="shell-topbar">
          <button className="shell-icon-btn" type="button" aria-label="折叠导航" onClick={toggleNavigation}>
            <IconMenu />
          </button>
          <div className="shell-page-meta">
            <div className="shell-page-kicker">工作台</div>
            <div className="shell-page-title">{activeItem.label}</div>
          </div>
          <div className="shell-topbar-fill" />
          <div className="shell-session" aria-label="当前 token 会话">
            <div className="shell-avatar">AD</div>
            <div className="shell-session-text">
              <div className="shell-session-name">admin</div>
              <div className="shell-session-sub">token 会话</div>
            </div>
          </div>
          <button className="shell-icon-btn" type="button" aria-label="退出登录" onClick={logout}>
            <IconExit />
          </button>
        </header>
        <main className="content">{children}</main>
      </div>
    </div>
  );
}
