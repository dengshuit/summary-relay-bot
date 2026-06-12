import React from 'react';
import {
  LayoutDashboard,
  Bot,
  Cpu,
  Users,
  History,
  LogOut,
  Menu,
  X,
  Code,
  ChevronLeft,
  ChevronRight,
  User,
  FileText,
  Send
} from 'lucide-react';

interface SidebarProps {
  currentTab: string;
  setTab: (tab: string) => void;
  onLogout: () => void;
}

export default function Sidebar({ currentTab, setTab, onLogout }: SidebarProps) {
  const [mobileOpen, setMobileOpen] = React.useState(false);
  const [isCollapsed, setIsCollapsed] = React.useState(false);
  const [hasManuallyToggled, setHasManuallyToggled] = React.useState(false);

  React.useEffect(() => {
    const handleResize = () => {
      if (hasManuallyToggled) return;
      if (window.innerWidth >= 1024 && window.innerWidth < 1280) {
        setIsCollapsed(true);
      } else if (window.innerWidth >= 1280) {
        setIsCollapsed(false);
      }
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, [hasManuallyToggled]);

  const menuItems = [
    { id: 'dashboard', label: '工作台', icon: LayoutDashboard },
    { id: 'bot', label: 'Bot 配置', icon: Bot },
    { id: 'engine', label: '摘要引擎', icon: Cpu },
    { id: 'groups', label: '群组管理', icon: Users },
    { id: 'private-relays', label: '私聊转发', icon: Send },
    { id: 'audit-logs', label: '审计日志', icon: History },
  ];

  const handleNav = (id: string) => {
    setTab(id);
    setMobileOpen(false);
  };

  return (
    <>
      {/* Mobile Top Header */}
      <header className="lg:hidden h-14 bg-white border-b border-gray-200 px-4 flex items-center justify-between sticky top-0 z-50">
        <div className="flex items-center gap-2.5">
          {/* SummaryBot brand icon */}
          <div className="w-8 h-8 flex items-center justify-center bg-transparent shrink-0">
            <svg className="w-7 h-7" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
              <g opacity="0.95">
                <path d="M20,17 C20,10 18,10 18,17 Z" fill="#a78bfa" />
                <path d="M20,23 C20,30 22,30 22,23 Z" fill="#a78bfa" />
                <path d="M17,20 C10,20 10,18 17,18 Z" fill="#a78bfa" />
                <path d="M23,20 C30,20 30,22 23,22 Z" fill="#a78bfa" />
                <path d="M17.5,17.5 C11.5,11.5 10,13 16,19 Z" fill="#a78bfa" />
                <path d="M22.5,22.5 C28.5,28.5 30,27 24,21 Z" fill="#a78bfa" />
                <path d="M22.5,17.5 C28.5,11.5 27,10 21,16 Z" fill="#a78bfa" />
                <path d="M17.5,22.5 C11.5,28.5 13,30 19,24 Z" fill="#a78bfa" />
                <circle cx="20" cy="20" r="1.5" fill="#ffffff" />
              </g>
              <path
                d="M23,26.5 C23,20 28,18 30.5,18 C31.5,18 32,19 30,21 C28.5,22 27,24 27.5,26.5"
                stroke="#7C3AED"
                strokeWidth="3.2"
                strokeLinecap="round"
                fill="none"
              />
            </svg>
          </div>
          <span className="font-bold text-[15px] text-gray-900 tracking-tight">SummaryBot</span>
        </div>
        <button
          onClick={() => setMobileOpen(!mobileOpen)}
          className="p-1 text-gray-500 hover:text-gray-900 focus:outline-none"
        >
          {mobileOpen ? <X className="w-6 h-6" /> : <Menu className="w-6 h-6" />}
        </button>
      </header>

      {/* Mobile Navigation Drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 bg-black/40 z-40 lg:hidden" onClick={() => setMobileOpen(false)}>
          <aside
            className="w-56 h-full bg-white flex flex-col pt-4 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 mb-6">
              <span className="text-xs font-semibold text-gray-400 uppercase tracking-wider">导航菜单</span>
            </div>
            <nav className="flex-1 px-3 space-y-1">
              {menuItems.map((item) => {
                const IconComp = item.icon;
                const active = currentTab === item.id || (item.id === 'groups' && currentTab.startsWith('group-detail:'));
                return (
                  <button
                    key={item.id}
                    onClick={() => handleNav(item.id)}
                    className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all ${
                      active
                        ? 'bg-[#EDE9FE] text-gray-900'
                        : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                    }`}
                  >
                    <IconComp className={`w-5 h-5 ${active ? 'text-gray-900' : 'text-gray-400'}`} />
                    {item.label}
                  </button>
                );
              })}
            </nav>
            <div className="p-4 border-t border-gray-100">
              {/* User Identity above Logout for mobile as well */}
              <div className="flex items-center gap-3 px-3 py-2 bg-gray-50 border border-gray-200/65 rounded-lg mb-3">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-extrabold text-[11px] shadow-[0_2px_4px_rgba(99,102,241,0.25)] shrink-0">
                  AD
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-gray-805">Admin</span>
                    <span className="w-2 h-2 rounded-full bg-green-500 inline-block animate-pulse" title="在线" />
                  </div>
                  <p className="text-[10px] text-gray-400 truncate">系统管理员</p>
                </div>
              </div>
              <button
                onClick={onLogout}
                className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium text-red-650 hover:bg-red-50 transition-all"
              >
                <LogOut className="w-5 h-5 text-red-400" />
                退出登录
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Desktop Sidebar */}
      <aside className={`hidden lg:flex border-r border-[#e4e6ec] bg-white h-screen flex-col sticky top-0 shrink-0 select-none relative transition-all duration-300 ${isCollapsed ? 'w-16' : 'w-52'}`}>
        {/* Floating border collapse/expand round bubble toggle matching the screenshot */}
        <button
          onClick={() => {
            setIsCollapsed(!isCollapsed);
            setHasManuallyToggled(true);
          }}
          className="absolute -right-3.5 top-[18px] z-40 flex items-center justify-center w-7 h-7 rounded-full border border-gray-200 bg-white shadow-[0_1px_2px_rgba(0,0,0,0.05)] hover:shadow-xs hover:scale-105 active:scale-95 text-gray-400 hover:text-gray-900 transition-all duration-200 cursor-pointer"
          title={isCollapsed ? "展开菜单" : "收起菜单"}
        >
          {isCollapsed ? (
            <ChevronRight className="w-4 h-4" />
          ) : (
            <ChevronLeft className="w-4 h-4" />
          )}
        </button>

        {/* Brand Header */}
        <div className={`h-16 border-b border-[#e4e6ec] flex items-center ${isCollapsed ? 'justify-center px-1' : 'justify-between px-5'}`}>
          {!isCollapsed ? (
            <div className="flex items-center gap-2 min-w-0">
              <div className="w-8 h-8 flex items-center justify-center bg-transparent shrink-0">
                <svg className="w-7.5 h-7.5" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                  <g opacity="0.95">
                    <path d="M20,17 C20,10 18,10 18,17 Z" fill="#a78bfa" />
                    <path d="M20,23 C20,30 22,30 22,23 Z" fill="#a78bfa" />
                    <path d="M17,20 C10,20 10,18 17,18 Z" fill="#a78bfa" />
                    <path d="M23,20 C30,20 30,22 23,22 Z" fill="#a78bfa" />
                    <path d="M17.5,17.5 C11.5,11.5 10,13 16,19 Z" fill="#a78bfa" />
                    <path d="M22.5,22.5 C28.5,28.5 30,27 24,21 Z" fill="#a78bfa" />
                    <path d="M22.5,17.5 C28.5,11.5 27,10 21,16 Z" fill="#a78bfa" />
                    <path d="M17.5,22.5 C11.5,28.5 13,30 19,24 Z" fill="#a78bfa" />
                    <circle cx="20" cy="20" r="1.5" fill="#ffffff" />
                  </g>
                  <path
                    d="M23,26.5 C23,20 28,18 30.5,18 C31.5,18 32,19 30,21 C28.5,22 27,24 27.5,26.5"
                    stroke="#7C3AED"
                    strokeWidth="3.2"
                    strokeLinecap="round"
                    fill="none"
                  />
                </svg>
              </div>
              <span className="font-extrabold text-sm text-[#111827] tracking-tight antialiased">
                SummaryBot
              </span>
            </div>
          ) : (
            <div className="w-8 h-8 flex items-center justify-center bg-transparent shrink-0">
              <svg className="w-7.5 h-7.5" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
                <g opacity="0.95">
                  <path d="M20,17 C20,10 18,10 18,17 Z" fill="#a78bfa" />
                  <path d="M20,23 C20,30 22,30 22,23 Z" fill="#a78bfa" />
                  <path d="M17,20 C10,20 10,18 17,18 Z" fill="#a78bfa" />
                  <path d="M23,20 C30,20 30,22 23,22 Z" fill="#a78bfa" />
                  <path d="M17.5,17.5 C11.5,11.5 10,13 16,19 Z" fill="#a78bfa" />
                  <path d="M22.5,22.5 C28.5,28.5 30,27 24,21 Z" fill="#a78bfa" />
                  <path d="M22.5,17.5 C28.5,11.5 27,10 21,16 Z" fill="#a78bfa" />
                  <path d="M17.5,22.5 C11.5,28.5 13,30 19,24 Z" fill="#a78bfa" />
                  <circle cx="20" cy="20" r="1.5" fill="#ffffff" />
                </g>
                <path
                  d="M23,26.5 C23,20 28,18 30.5,18 C31.5,18 32,19 30,21 C28.5,22 27,24 27.5,26.5"
                  stroke="#7C3AED"
                  strokeWidth="3.2"
                  strokeLinecap="round"
                  fill="none"
                />
              </svg>
            </div>
          )}
        </div>

        {/* Menu Navigation */}
        <nav className="flex-1 py-6 px-3 space-y-2 overflow-y-auto">
          {menuItems.map((item) => {
            const IconComp = item.icon;
            const active = currentTab === item.id || (item.id === 'groups' && currentTab.startsWith('group-detail-'));
            return (
              <button
                key={item.id}
                onClick={() => setTab(item.id)}
                title={isCollapsed ? item.label : undefined}
                className={`w-full flex items-center rounded-lg text-[14px] font-medium transition-all ${
                  isCollapsed ? 'justify-center p-3' : 'gap-3 px-3.5 py-2.5'
                } ${
                  active
                    ? 'bg-[#EDE9FE] text-[#111827] shadow-2xs'
                    : 'text-[#4B5563] hover:bg-gray-50 hover:text-[#111827]'
                }`}
              >
                <IconComp className={`w-[18px] h-[18px] ${active ? 'text-[#111827]' : 'text-gray-400'} shrink-0`} />
                {!isCollapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Harmonious Footer - Admin info and Logout integrated on the same line */}
        <div className="p-3 border-t border-[#e4e6ec] bg-[#fafafa]/50">
          {!isCollapsed ? (
            <div className="flex items-center justify-between gap-2 p-2 px-2.5 bg-gray-50 border border-gray-250/20 rounded-xl shadow-[0_1px_2px_rgba(0,0,0,0.02)]">
              <div className="flex items-center gap-2 min-w-0">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-extrabold text-[11px] shadow-[0_2px_4px_rgba(99,102,241,0.25)] shrink-0">
                  AD
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-1">
                    <span className="text-xs font-extrabold text-[#374151] tracking-wide">Admin</span>
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 inline-block shrink-0" title="在线" />
                  </div>
                  <p className="text-[10px] text-gray-405 truncate font-medium">管理员</p>
                </div>
              </div>

              <button
                onClick={onLogout}
                title="退出登录"
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-650 hover:bg-red-50/70 hover:border-red-100 border border-transparent transition-all cursor-pointer shrink-0"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          ) : (
            <div className="flex flex-col items-center gap-3 py-1">
              <div className="relative group cursor-help" title="Admin (系统管理员)">
                <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-indigo-500 to-purple-500 flex items-center justify-center text-white font-extrabold text-[11px] shadow-[0_2px_4px_rgba(99,102,241,0.25)] shrink-0">
                  AD
                </div>
                <span className="absolute bottom-0 right-0 w-2 h-2 rounded-full bg-emerald-500 border border-white" />
              </div>

              <button
                onClick={onLogout}
                title="退出登录"
                className="p-1.5 rounded-lg text-gray-400 hover:text-red-650 hover:bg-red-50 hover:border-red-100 border border-transparent transition-all cursor-pointer"
              >
                <LogOut className="w-4 h-4" />
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
