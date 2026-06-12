import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { PrivateRelayItem, PrivateRelaysResponse, PrivateUser } from '../api/types';
import {
  Send,
  Search,
  MessageSquare,
  Check,
  CheckCircle,
  AlertTriangle,
  XCircle,
  Clock,
  RefreshCw,
  X,
  User,
  ChevronRight,
  Info,
  ShieldCheck,
  AlertCircle,
  Eye,
  ArrowLeft,
  ChevronDown,
  Terminal,
  Paperclip
} from 'lucide-react';
import CustomSelect from '../components/CustomSelect';

interface PrivateSession {
  user_id: number;
  private_user: PrivateUser;
  recent_message: string;
  recent_active_time: string;
  incoming_count: number;
  outgoing_count: number;
  delivery_status: 'normal' | 'partial_failed' | 'failed' | 'blocked';
  recent_error: string | null;
  items: PrivateRelayItem[];
}

export default function PrivateRelays() {
  const [rawData, setRawData] = useState<PrivateRelayItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  // Filters
  const [searchQuery, setSearchQuery] = useState('');
  const [sessionStatus, setSessionStatus] = useState('');
  const [triggerQuery, setTriggerQuery] = useState('');

  // Sessions list
  const [sessions, setSessions] = useState<PrivateSession[]>([]);
  // Open session detail inside high-end modal dialog instead of flat view splitscreen
  const [selectedSession, setSelectedSession] = useState<PrivateSession | null>(null);

  // Track expanded details state for message IDs inside bubbles
  const [expandedDetailsMap, setExpandedDetailsMap] = useState<Record<string, boolean>>({});

  const fetchRelays = async (manual = false) => {
    setLoading(true);
    if (!manual) {
      setErrorText(null);
    }
    try {
      const res = await api.getPrivateRelays({});
      if (res && res.items) {
        setRawData(res.items);
      }
    } catch (err: any) {
      setRawData([]);
      setErrorText(err.message || '获取私聊转发记录遭到异常阻断');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRelays();
  }, [triggerQuery]);

  // Aggregate raw flat array into clean conversational sessions
  useEffect(() => {
    if (!rawData) return;

    const map = new Map<number, PrivateSession>();

    // Sort oldest to newest so they append in standard WeChat chronological order inside the messages array
    const sortedItems = [...rawData].sort(
      (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime()
    );

    for (const item of sortedItems) {
      const u = item.private_user;
      const key = u.telegram_user_id;
      let session = map.get(key);

      if (!session) {
        session = {
          user_id: key,
          private_user: u,
          recent_message: item.text_preview || item.caption_preview || '多媒体资源/非文本消息',
          recent_active_time: item.created_at,
          incoming_count: 0,
          outgoing_count: 0,
          delivery_status: 'normal',
          recent_error: null,
          items: []
        };
        map.set(key, session);
      }

      session.items.push(item);
      session.recent_message = item.text_preview || item.caption_preview || '多媒体资源/非文本消息';
      session.recent_active_time = item.created_at;

      if (item.direction === 'incoming') {
        session.incoming_count += 1;
      } else if (item.direction === 'outgoing') {
        session.outgoing_count += 1;
      }

      // Prioritize error state: blocked > failed > partial_failed > normal
      if (item.delivery_status === 'blocked') {
        session.delivery_status = 'blocked';
        session.recent_error = item.error_message || item.error_type || '主人端被拦截/用户已封锁';
      } else if (item.delivery_status === 'failed' && session.delivery_status !== 'blocked') {
        session.delivery_status = 'failed';
        session.recent_error = item.error_message || item.error_type || '上行投递通讯通道失效';
      } else if (item.delivery_status === 'partial_failed' && session.delivery_status !== 'blocked' && session.delivery_status !== 'failed') {
        session.delivery_status = 'partial_failed';
        session.recent_error = item.error_message || item.error_type || '部分中转节点无法触达';
      }
    }

    // Convert map to list
    const sessionList = Array.from(map.values());

    // Perform front-end indexing & queries
    const filtered = sessionList.filter(s => {
      // 1. Search Query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const tgId = String(s.user_id).toLowerCase();
        const username = (s.private_user.username || '').toLowerCase();
        const fName = (s.private_user.first_name || '').toLowerCase();
        const lName = (s.private_user.last_name || '').toLowerCase();
        const recentMsg = s.recent_message.toLowerCase();

        const matchesSearch =
          tgId.includes(q) ||
          username.includes(q) ||
          fName.includes(q) ||
          lName.includes(q) ||
          recentMsg.includes(q);

        if (!matchesSearch) return false;
      }

      // 2. Status Filter
      if (sessionStatus) {
        if (sessionStatus === 'normal' && s.delivery_status !== 'normal') return false;
        if (sessionStatus === 'failed' && s.delivery_status !== 'failed') return false;
        if (sessionStatus === 'blocked' && s.delivery_status !== 'blocked') return false;
        if (sessionStatus === 'partial_failed' && s.delivery_status !== 'partial_failed') return false;
        if (sessionStatus === 'error' && s.delivery_status === 'normal') return false; // Any error
      }

      return true;
    });

    // Sort by recent active time descending so newly updated chats jump to top
    filtered.sort((a, b) => new Date(b.recent_active_time).getTime() - new Date(a.recent_active_time).getTime());

    setSessions(filtered);

    // Keep currently selected session perfectly reactive if its underlying items updated
    if (selectedSession) {
      const updatedSelect = filtered.find(s => s.user_id === selectedSession.user_id);
      if (updatedSelect) {
        setSelectedSession(updatedSelect);
      }
    }
  }, [rawData, searchQuery, sessionStatus]);

  const clearFilters = () => {
    setSearchQuery('');
    setSessionStatus('');
    setTriggerQuery('');
  };

  const toggleTechnicalDetail = (msgId: number | string) => {
    const key = String(msgId);
    setExpandedDetailsMap(prev => ({
      ...prev,
      [key]: !prev[key]
    }));
  };

  // Dynamic status badges for listing
  const getSessionStatusBadge = (statusStr: 'normal' | 'partial_failed' | 'failed' | 'blocked') => {
    switch (statusStr) {
      case 'normal':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-150 shrink-0 select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            正常
          </span>
        );
      case 'partial_failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shrink-0 select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-500 animate-pulse" />
            部分失败
          </span>
        );
      case 'failed':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-250 shrink-0 select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
            失败
          </span>
        );
      case 'blocked':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-red-50 text-red-700 border border-red-150 shrink-0 select-none">
            <span className="w-1.5 h-1.5 rounded-full bg-red-500" />
            已阻塞
          </span>
        );
    }
  };

  const getMsgStatusIcon = (statusStr: string) => {
    switch (statusStr) {
      case 'sent':
        return <span title="发送成功"><Check className="w-3.5 h-3.5 text-emerald-500" /></span>;
      case 'failed':
        return <span title="发送失败"><XCircle className="w-3.5 h-3.5 text-rose-500" /></span>;
      case 'blocked':
        return <span title="用户拦截"><AlertCircle className="w-3.5 h-3.5 text-amber-500" /></span>;
      default:
        return <span title="队列中"><Clock className="w-3.5 h-3.5 text-gray-400" /></span>;
    }
  };

  // Dynamic statistics calculations
  const totalUsers = sessions.length;
  const last24hIncoming = rawData.filter(
    item => item.direction === 'incoming' && new Date(item.created_at).getTime() > Date.now() - 24 * 3600 * 1000
  ).length;
  const last24hOutgoing = rawData.filter(
    item => item.direction === 'outgoing' && new Date(item.created_at).getTime() > Date.now() - 24 * 3600 * 1000
  ).length;
  const errorSessionsCount = sessions.filter(s => s.delivery_status !== 'normal').length;

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">

      {/* Page Title & Refresh */}
      <div className="flex justify-between items-center animate-in fade-in slide-in-from-top-4 duration-200">
        <div>
          <h2 className="text-[24px] font-semibold text-gray-900 leading-none">私聊转发</h2>
        </div>
        <button
          onClick={() => fetchRelays(true)}
          disabled={loading}
          className="p-2.5 border border-[#e4e6ec] bg-white text-gray-505 hover:text-indigo-600 hover:bg-gray-50 rounded-lg cursor-pointer transition-all disabled:opacity-40 flex items-center gap-1.5 text-xs font-bold shadow-2xs"
          title="强制拉取最新事件"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          <span>同步日志</span>
        </button>
      </div>

      {/* 24-Hour Adaptive Statistics Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 animate-in fade-in slide-in-from-top-3 duration-200 delay-75">
        <div className="bg-white p-4 rounded-xl border border-[#e4e6ec] shadow-sm flex flex-col justify-between">
          <span className="text-[11px] font-bold text-gray-400 block uppercase tracking-wider">私聊用户数</span>
          <div className="flex items-baseline gap-2 mt-1.5">
            <span className="text-2xl font-black text-gray-900 font-mono leading-none">
              {totalUsers}
            </span>
            <span className="text-[10px] text-gray-400 font-bold">个会话终端</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#e4e6ec] shadow-sm flex flex-col justify-between">
          <span className="text-[11px] font-bold text-gray-400 block uppercase tracking-wider">近 24h 入站消息</span>
          <div className="flex items-baseline gap-2 mt-1.5">
            <span className="text-2xl font-black text-indigo-600 font-mono leading-none">
              {last24hIncoming}
            </span>
            <span className="text-[10px] text-gray-400 font-bold">条用户消息</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#e4e6ec] shadow-sm flex flex-col justify-between">
          <span className="text-[11px] font-bold text-emerald-500 block uppercase tracking-wider">近 24h 出站回复</span>
          <div className="flex items-baseline gap-2 mt-1.5">
            <span className="text-2xl font-black text-emerald-600 font-mono leading-none">
              {last24hOutgoing}
            </span>
            <span className="text-[10px] text-emerald-400 font-bold">条主人回复</span>
          </div>
        </div>

        <div className="bg-white p-4 rounded-xl border border-[#e4e6ec] shadow-sm flex flex-col justify-between">
          <span className="text-[11px] font-bold text-rose-500 block uppercase tracking-wider">异常会话数</span>
          <div className="flex items-baseline gap-1.5 mt-1.5">
            <span className={`text-2xl font-black font-mono leading-none ${errorSessionsCount > 0 ? 'text-rose-600' : 'text-gray-905'}`}>
              {errorSessionsCount}
            </span>
            <span className="text-[10px] text-rose-400 font-bold">组通信中断</span>
          </div>
        </div>
      </div>

      {/* Filter Options */}
      <div className="bg-white rounded-xl border border-gray-100 p-4 shadow-[0_4px_12px_rgba(0,0,0,0.03)] grid grid-cols-1 md:grid-cols-12 gap-3.5 items-center z-20 relative animate-in fade-in slide-in-from-top-3 duration-200 delay-100">
        <div className="relative md:col-span-5">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-indigo-500 pointer-events-none">
            <Search className="w-4 h-4" />
          </span>
          <input
            type="text"
            placeholder="搜索用户名 / Telegram User ID / 最近消息预览..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-8 py-2 bg-gray-50/50 hover:bg-gray-50 border border-gray-200 focus:border-indigo-500 focus:bg-white rounded-lg text-[13px] text-gray-800 placeholder-gray-400 focus:outline-none focus:ring-4 focus:ring-indigo-50/70 h-[36px] leading-normal transition-all"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute inset-y-0 right-0 pr-2.5 flex items-center text-gray-400 hover:text-gray-600 transition-colors"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>

        <div className="md:col-span-4 z-10">
          <CustomSelect
            options={[
              { value: "", label: "全部会话状态" },
              { value: "normal", label: "正常正常并发送 (normal)" },
              { value: "partial_failed", label: "部分中转失败 (partial_failed)" },
              { value: "failed", label: "投递已失败 (failed)" },
              { value: "blocked", label: "被用户单防屏蔽 (blocked)" },
              { value: "error", label: "所有受干扰异常会话" }
            ]}
            value={sessionStatus}
            onChange={(val) => setSessionStatus(val)}
            placeholder="会话状态筛选"
            className="h-[36px]"
          />
        </div>

        <div className="md:col-span-3 flex gap-2 h-[36px]">
          <button
            onClick={() => setTriggerQuery(searchQuery + Math.random())}
            className="flex-1 bg-indigo-600 hover:bg-indigo-700 active:scale-[0.98] text-white rounded-lg text-xs font-bold leading-none shadow-[0_2px_4px_rgba(79,70,229,0.15)] hover:shadow-[0_4px_8px_rgba(79,70,229,0.25)] transition-all cursor-pointer flex items-center justify-center gap-1.5 h-full"
          >
            <Search className="w-3.5 h-3.5" />
            <span>复合检索</span>
          </button>
          {(searchQuery || sessionStatus) && (
            <button
              onClick={clearFilters}
              className="px-3 border border-gray-250 hover:bg-gray-50 text-gray-500 hover:text-gray-700 rounded-lg text-xs font-semibold hover:border-gray-300 transition-all cursor-pointer flex items-center justify-center gap-1 h-full"
            >
              <span>重置</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Single list display (Table structure) taking full page width */}
      <div className="bg-white rounded-xl border border-[#e4e6ec] overflow-hidden shadow-sm">
        <div className="p-4 border-b border-gray-100 bg-slate-50/40 flex justify-between items-center">
          <span className="text-xs font-extrabold text-gray-500 uppercase tracking-widest">
            私聊会话列表 ({sessions.length})
          </span>
        </div>

        {loading ? (
          <div className="p-16 flex flex-col items-center justify-center space-y-3">
            <RefreshCw className="w-8 h-8 text-indigo-500 animate-spin" />
            <p className="text-xs font-bold text-gray-500">正在拉取私聊转发检测数据...</p>
          </div>
        ) : sessions.length === 0 ? (
          <div className="p-16 text-center space-y-3">
            <MessageSquare className="w-10 h-10 text-gray-305 mx-auto" />
            <div className="max-w-xs mx-auto">
              <h4 className="text-sm font-bold text-gray-800">未检索到任何符合的私聊会话</h4>
              <p className="text-xs text-gray-400 mt-1">请尝试调整搜索词，或是清除筛选条件重新检索。</p>
            </div>
            <button
              onClick={clearFilters}
              className="mt-2 px-3 py-1.5 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg text-xs font-bold text-gray-650 transition-colors"
            >
              重置过滤器
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse table-auto">
              <thead>
                <tr className="border-b border-gray-100 bg-gray-50/55 text-[11px] font-extrabold text-gray-400 uppercase tracking-wider">
                  <th className="px-5 py-3.5">用户</th>
                  <th className="px-5 py-3.5">Telegram User ID</th>
                  <th className="px-5 py-3.5">最近活跃时间</th>
                  <th className="px-5 py-3.5 text-center">In / Out 流量数</th>
                  <th className="px-5 py-3.5">会话状态</th>
                  <th className="px-5 py-3.5 text-center">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 text-[14px] text-gray-700">
                {sessions.map((session) => (
                  <tr
                    key={session.user_id}
                    className="hover:bg-slate-50/40 transition-colors group"
                  >
                    {/* Column 1: User Profile visual info */}
                    <td className="px-5 py-3.5 max-w-[200px]">
                      <div className="flex items-center gap-2.5">
                        <div className="w-8 h-8 rounded-full bg-slate-100 border border-slate-200/60 flex items-center justify-center shrink-0 text-xs font-bold text-slate-600">
                          {session.private_user.first_name ? session.private_user.first_name[0].toUpperCase() : 'U'}
                        </div>
                        <div className="min-w-0">
                          <div className="font-bold text-gray-850 truncate leading-tight">
                            {session.private_user.first_name} {session.private_user.last_name || ''}
                          </div>
                          {session.private_user.username && (
                            <div className="text-[10px] text-gray-500 font-medium mt-0.5 truncate">
                              @{session.private_user.username}
                            </div>
                          )}
                        </div>
                      </div>
                    </td>

                    {/* Column 2: Telegram User ID */}
                    <td className="px-5 py-3.5 font-mono text-[11px] text-gray-500 whitespace-nowrap">
                      {session.user_id}
                    </td>

                    {/* Column 4: Last Active Time */}
                    <td className="px-5 py-3.5 text-gray-500 whitespace-nowrap font-mono text-[11px]">
                      {new Date(session.recent_active_time).toLocaleString('zh-CN', {
                        month: 'numeric',
                        day: 'numeric',
                        hour: '2-digit',
                        minute: '2-digit'
                      })}
                    </td>

                    {/* Column 5: Incoming vs Outgoing count */}
                    <td className="px-5 py-3.5 text-center whitespace-nowrap font-mono text-[11px]">
                      <span className="px-2 py-0.5 rounded bg-blue-50 text-blue-600 border border-blue-100" title="入向">
                        📥 {session.incoming_count}
                      </span>
                      <span className="mx-1 text-gray-305">/</span>
                      <span className="px-2 py-0.5 rounded bg-gray-50 text-gray-600 border border-gray-200/50" title="出回复">
                        📤 {session.outgoing_count}
                      </span>
                    </td>

                    {/* Column 6: Status Badge */}
                    <td className="px-5 py-3.5 whitespace-nowrap">
                      {getSessionStatusBadge(session.delivery_status)}
                    </td>

                    {/* Column 7: Dialog View Trigger Action */}
                    <td className="px-5 py-3.5 text-center whitespace-nowrap">
                      <button
                        onClick={() => setSelectedSession(session)}
                        className="px-2.5 py-1.5 text-xs font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50/50 hover:bg-indigo-50 border border-indigo-100/80 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1 shrink-0"
                      >
                        <Eye className="w-3.5 h-3.5" />
                        <span>查看</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Pop-up dialog modal representing the WeChat-style conversation timeline */}
      {selectedSession && (
        <div className="fixed inset-0 z-50 overflow-y-auto flex items-center justify-center p-4" aria-labelledby="chat-modal-title" role="dialog" aria-modal="true">
          {/* Backdrop screen */}
          <div
            className="fixed inset-0 bg-black/45 backdrop-blur-xs transition-opacity duration-200 animate-in fade-in"
            onClick={() => setSelectedSession(null)}
          />

          {/* Modal content viewport */}
          <div className="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl overflow-hidden flex flex-col h-[700px] max-h-[90vh] border border-gray-200/50 animate-in zoom-in-95 duration-150">

            {/* Header section with profile overview */}
            <div className="px-5 py-4 border-b border-slate-100 bg-slate-50 flex justify-between items-center shrink-0">
              <div className="flex items-center gap-2.5">
                <div className="w-10 h-10 rounded-full bg-gray-100 border border-gray-200 flex items-center justify-center font-bold text-gray-700 text-sm">
                  {selectedSession.private_user.first_name ? selectedSession.private_user.first_name[0].toUpperCase() : 'U'}
                </div>
                <div className="text-left">
                  <h3 id="chat-modal-title" className="font-extrabold text-gray-901 text-[13.5px] leading-tight flex items-center gap-1.5">
                    <span>{selectedSession.private_user.first_name} {selectedSession.private_user.last_name || ''}</span>
                    <span className="text-[10px] bg-slate-200 text-gray-500 font-bold px-1.5 py-0.2 rounded font-mono">
                      User ID: {selectedSession.user_id}
                    </span>
                  </h3>
                  {selectedSession.private_user.username && (
                    <span className="text-[10px] text-gray-500 font-medium block mt-1">
                      Telegram Username: @{selectedSession.private_user.username}
                    </span>
                  )}
                </div>
              </div>

              {/* Status and Action controls */}
              <div className="flex items-center gap-3">
                <div className="flex items-center gap-1.5">
                  <span className="text-[10px] text-gray-400 font-bold">通讯诊断：</span>
                  {getSessionStatusBadge(selectedSession.delivery_status)}
                </div>
                <button
                  onClick={() => setSelectedSession(null)}
                  className="p-1 rounded-lg hover:bg-gray-200 text-gray-400 hover:text-gray-700 transition-colors"
                  aria-label="关闭对话"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Scrolling Timeline content designed strictly like WeChat green/slate message buckets */}
            <div className="flex-1 overflow-y-auto bg-slate-50/60 p-5 space-y-4">

              {/* Information disclaimer box */}
              <div className="text-center">
                <span className="inline-block px-3 py-1 bg-gray-100/80 text-gray-400 rounded-full text-[10px] font-bold">
                  🛡️ 只读检测观测视图，本后台无权修改或上行动作
                </span>
              </div>

              {selectedSession.items.map((item) => {
                const isOutgoing = item.direction === 'outgoing';
                const hasDetails = expandedDetailsMap[String(item.id)];

                return (
                  <div
                    key={item.id}
                    className={`flex gap-3 ${isOutgoing ? 'flex-row-reverse' : ''}`}
                  >
                    {/* Human/Agent avatar indicator */}
                    <div className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold shrink-0 ${
                      isOutgoing
                        ? 'bg-indigo-600 text-white shadow-2xs'
                        : 'bg-slate-250 text-gray-650 border border-slate-350/50 shadow-2xs'
                    }`}>
                      {isOutgoing ? '主' : (selectedSession.private_user.first_name ? selectedSession.private_user.first_name[0].toUpperCase() : 'U')}
                    </div>

                    {/* Speech bubble frame */}
                    <div className={`flex flex-col max-w-[75%] ${isOutgoing ? 'items-end' : 'items-start'}`}>
                      {/* Meta small labels */}
                      <div className="flex items-center gap-1.5 mb-0.5 text-[9px] text-gray-405 font-bold uppercase">
                        <span>{item.message_type}</span>
                        {!isOutgoing && <span className="bg-slate-200 text-[8px] px-1 rounded font-bold text-gray-500">用户入站</span>}
                        {isOutgoing && <span className="bg-indigo-100 text-[8px] px-1 rounded font-bold text-indigo-600">下行回复</span>}
                      </div>

                      {/* Actual speech balloon with different colors (WeChat wechat-inspired palette) */}
                      <div className={`p-3 rounded-2xl shadow-2xs leading-relaxed text-[12.5px] font-medium text-left ${
                        isOutgoing
                          ? 'bg-indigo-600 text-white rounded-tr-none'
                          : 'bg-white text-gray-850 border border-slate-200/70 rounded-tl-none'
                      }`}>
                        {item.message_type === 'photo' && (
                          <div className="flex items-center gap-1.5 mb-1.5 py-1 px-2 rounded bg-black/10 text-2xs font-bold">
                            <Paperclip className="w-3 h-3" />
                            <span>Telegram 多媒体图片载入</span>
                          </div>
                        )}

                        {item.text_preview || item.caption_preview ? (
                          <p className="whitespace-pre-wrap">{item.text_preview || item.caption_preview}</p>
                        ) : (
                          <p className="italic text-gray-400 font-normal">多媒体资源 (未载入文本描述 / 已被安全省略)</p>
                        )}
                      </div>

                      {/* Beneath bubble actions */}
                      <div className="flex items-center gap-1.5 mt-1 text-[10px] text-gray-400">
                        <span>
                          {new Date(item.created_at).toLocaleString('zh-CN', {
                            hour: '2-digit',
                            minute: '2-digit',
                            second: '2-digit'
                          })}
                        </span>
                        {isOutgoing && getMsgStatusIcon(item.delivery_status)}

                        <button
                          onClick={() => toggleTechnicalDetail(item.id)}
                          className="text-indigo-600 hover:text-indigo-800 font-bold focus:outline-none ml-1 cursor-pointer text-[10px]"
                        >
                          {hasDetails ? '收起系统参数 ↑' : '系统参数...'}
                        </button>
                      </div>

                      {/* Error reporting */}
                      {item.error_message && (
                        <div className="mt-1.5 p-2 bg-rose-50 border border-rose-100 rounded-lg text-[10px] text-rose-700 font-mono w-full text-left">
                          <strong>失败反馈：</strong>{item.error_message} (代码: {item.error_type})
                        </div>
                      )}

                      {/* Collapsible Tech Param panel block */}
                      {hasDetails && (
                        <div className="mt-2 p-2.5 bg-slate-900 text-slate-300 text-[10px] font-mono rounded-lg w-full text-left space-y-1 shadow-inner animate-in fade-in duration-100">
                          <div className="text-indigo-405 font-bold border-b border-slate-700 pb-1 flex items-center gap-1">
                            <Terminal className="w-3 h-3 text-indigo-400" />
                            <span>Telegram Payload Metadata</span>
                          </div>
                          <p><span className="text-slate-500">Msg ID:</span> {item.telegram_message_id || 'null'}</p>
                          <p><span className="text-slate-500">Admin Msg ID:</span> {item.admin_message_id || 'null'}</p>
                          <p><span className="text-slate-500">Status:</span> {item.delivery_status}</p>
                          {item.reply_maps && item.reply_maps.length > 0 ? (
                            <div>
                              <span className="text-slate-500">Reply Maps:</span>
                              {item.reply_maps.map((m, i) => (
                                <div key={i} className="pl-2 text-slate-400 text-[9px]">
                                  ↳ {m.source_kind} [{m.status}] → admin_id: {m.admin_message_id}
                                </div>
                              ))}
                            </div>
                          ) : (
                            <p><span className="text-slate-500">Reply Maps:</span> 无关联路由</p>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Read-Only Notice bottom bar layout */}
            <div className="p-4 border-t border-slate-100 bg-slate-50 text-center text-xs text-gray-500 flex items-center justify-between shrink-0">
              <div className="flex items-center gap-1.5">
                <ShieldCheck className="w-4 h-4 text-emerald-500 shrink-0" />
                <span className="font-medium">此终端处于审计保护机制中，禁止反传任何更改。</span>
              </div>
              <button
                type="button"
                onClick={() => setSelectedSession(null)}
                className="px-4 py-1.5 border border-gray-300 hover:bg-gray-100 text-gray-700 bg-white rounded-lg text-xs font-semibold shadow-2xs transition-colors cursor-pointer"
              >
                关闭
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
