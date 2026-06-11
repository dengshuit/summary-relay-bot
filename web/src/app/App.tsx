import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { getStoredToken } from "../api/client";
import { AppShell } from "../components/AppShell";
import { AuditLogs } from "../pages/AuditLogs";
import { Bot } from "../pages/Bot";
import { ComponentReference } from "../pages/ComponentReference";
import { Dashboard } from "../pages/Dashboard";
import { Engine } from "../pages/Engine";
import { GroupDetail } from "../pages/GroupDetail";
import { Groups } from "../pages/Groups";
import { Login } from "../pages/Login";

function RequireAuth({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const hasToken = Boolean(getStoredToken());
  if (!hasToken) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <AppShell>{children}</AppShell>;
}

export function App() {
  const navigate = useNavigate();
  const [sessionVersion, setSessionVersion] = useState(0);

  useEffect(() => {
    const onUnauthorized = () => {
      setSessionVersion((version) => version + 1);
      navigate("/login", { replace: true, state: { authFailed: true } });
    };
    window.addEventListener("webui:unauthorized", onUnauthorized);
    return () => window.removeEventListener("webui:unauthorized", onUnauthorized);
  }, [navigate]);

  const routes = useMemo(
    () => (
      <Routes key={sessionVersion}>
        <Route path="/login" element={<Login />} />
        <Route path="/component-reference" element={<ComponentReference />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />
        <Route
          path="/bot"
          element={
            <RequireAuth>
              <Bot />
            </RequireAuth>
          }
        />
        <Route
          path="/engine"
          element={
            <RequireAuth>
              <Engine />
            </RequireAuth>
          }
        />
        <Route
          path="/groups"
          element={
            <RequireAuth>
              <Groups />
            </RequireAuth>
          }
        />
        <Route
          path="/groups/:groupId"
          element={
            <RequireAuth>
              <GroupDetail />
            </RequireAuth>
          }
        />
        <Route
          path="/audit-logs"
          element={
            <RequireAuth>
              <AuditLogs />
            </RequireAuth>
          }
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    ),
    [sessionVersion]
  );

  return routes;
}
