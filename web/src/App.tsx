import React, { useEffect, useState } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useNavigate,
  useParams,
  useLocation
} from 'react-router-dom';
import { getStoredToken, isAuthenticated, clearStoredToken } from './api/client';

// Views
import Login from './views/Login';
import Dashboard from './views/Dashboard';
import BotConfig from './views/Bot';
import Userbot from './views/Userbot';
import Engine from './views/Engine';
import Groups from './views/Groups';
import GroupDetail from './views/GroupDetail';
import AuditLogs from './views/AuditLogs';
import Summaries from './views/Summaries';
import ComponentReference from './views/ComponentReference';
import PrivateRelays from './views/PrivateRelays';

// Layout & Components
import Sidebar from './components/Sidebar';
import TopProgressBar from './components/TopProgressBar';
import { ToastProvider } from './components/Toast';

function PrivateLayout({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const location = useLocation();
  const token = getStoredToken();

  if (!token) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  // Handle mapping react-router route paths to highlighting sidebar indices
  const getActiveTab = () => {
    const path = location.pathname;
    if (path === '/') return 'dashboard';
    if (path.startsWith('/bot')) return 'bot';
    if (path.startsWith('/userbot')) return 'userbot';
    if (path.startsWith('/engine')) return 'engine';
    if (path.startsWith('/groups')) return 'groups';
    if (path.startsWith('/summaries')) return 'summaries';
    if (path.startsWith('/private-relays')) return 'private-relays';
    if (path.startsWith('/audit-logs')) return 'audit-logs';
    return 'dashboard';
  };

  const handleTabChange = (tab: string) => {
    if (tab === 'dashboard') navigate('/');
    else if (tab === 'bot') navigate('/bot');
    else if (tab === 'userbot') navigate('/userbot');
    else if (tab === 'engine') navigate('/engine');
    else if (tab === 'groups') navigate('/groups');
    else if (tab === 'summaries') navigate('/summaries');
    else if (tab === 'private-relays') navigate('/private-relays');
    else if (tab === 'audit-logs') navigate('/audit-logs');
  };

  const handleLogout = () => {
    clearStoredToken();
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-[#f6f7fb] overflow-hidden selection:bg-indigo-100">
      {/* Dynamic Navigation Progress Bar */}
      <TopProgressBar />

      {/* Sidebar Layout component */}
      <Sidebar
        currentTab={getActiveTab()}
        setTab={handleTabChange}
        onLogout={handleLogout}
      />

      {/* Main viewport area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-y-auto">
        <main className="flex-1">
          {children}
        </main>
      </div>
    </div>
  );
}

// Wrapper for group detail to extract id
function GroupDetailWrapper() {
  const { groupId } = useParams<{ groupId: string }>();
  const navigate = useNavigate();

  if (!groupId) {
    return <Navigate to="/groups" replace />;
  }

  return (
    <GroupDetail
      groupId={groupId}
      onBack={() => navigate('/groups')}
    />
  );
}

function MainApp() {
  const navigate = useNavigate();
  const [token, setToken] = useState<string | null>(getStoredToken());

  useEffect(() => {
    const handleUnauthorized = () => {
      clearStoredToken();
      setToken(null);
      navigate('/login');
    };

    window.addEventListener('api-unauthorized', handleUnauthorized);
    return () => {
      window.removeEventListener('api-unauthorized', handleUnauthorized);
    };
  }, [navigate]);

  return (
    <Routes>
      {/* Auth Screen */}
      <Route
        path="/login"
        element={
          token ? (
            <Navigate to="/" replace />
          ) : (
            <Login onLoginSuccess={(t) => { setToken(t); navigate('/'); }} />
          )
        }
      />

      {/* Hidden dev visual reference mapping page */}
      <Route
        path="/component-reference"
        element={
          <PrivateLayout>
            <ComponentReference />
          </PrivateLayout>
        }
      />

      {/* Primary operator routes */}
      <Route
        path="/"
        element={
          <PrivateLayout>
            <Dashboard
              setTab={(tab) => {
                // If dashboard trigger navigation (e.g. modify config)
                if (tab === 'bot') navigate('/bot');
                else if (tab === 'userbot') navigate('/userbot');
                else if (tab === 'engine') navigate('/engine');
                else if (tab === 'groups') navigate('/groups');
                else if (tab === 'summaries') navigate('/summaries');
                else if (tab === 'audit-logs') navigate('/audit-logs');
                else if (tab.startsWith('group-detail-')) {
                  const id = tab.replace('group-detail-', '');
                  navigate(`/groups/${id}`);
                }
              }}
            />
          </PrivateLayout>
        }
      />

      <Route
        path="/bot"
        element={
          <PrivateLayout>
            <BotConfig />
          </PrivateLayout>
        }
      />

      <Route
        path="/userbot"
        element={
          <PrivateLayout>
            <Userbot />
          </PrivateLayout>
        }
      />

      <Route
        path="/engine"
        element={
          <PrivateLayout>
            <Engine />
          </PrivateLayout>
        }
      />

      <Route
        path="/groups"
        element={
          <PrivateLayout>
            <Groups
              setTab={(tab) => {
                if (tab.startsWith('group-detail-')) {
                  const id = tab.replace('group-detail-', '');
                  navigate(`/groups/${id}`);
                }
              }}
              setSelectedGroupId={() => {}}
            />
          </PrivateLayout>
        }
      />

      <Route
        path="/groups/:groupId"
        element={
          <PrivateLayout>
            <GroupDetailWrapper />
          </PrivateLayout>
        }
      />

      <Route
        path="/summaries"
        element={
          <PrivateLayout>
            <Summaries />
          </PrivateLayout>
        }
      />

      <Route
        path="/audit-logs"
        element={
          <PrivateLayout>
            <AuditLogs />
          </PrivateLayout>
        }
      />

      <Route
        path="/private-relays"
        element={
          <PrivateLayout>
            <PrivateRelays />
          </PrivateLayout>
        }
      />

      {/* Fallback redirection */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <MainApp />
      </ToastProvider>
    </BrowserRouter>
  );
}
