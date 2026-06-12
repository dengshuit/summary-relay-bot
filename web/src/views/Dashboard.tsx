import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { DashboardData, GroupItem, PrivateRelayItem } from '../api/types';
import {
  RefreshCw,
  Bot,
  Users,
  FileText,
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Clock,
  User,
  History,
  TrendingUp,
  Workflow,
  MessageSquare
} from 'lucide-react';
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell
} from 'recharts';

interface DashboardProps {
  setTab: (tab: string) => void;
  setSelectedGroupId: (id: string | null) => void;
}

export default function Dashboard({ setTab, setSelectedGroupId }: DashboardProps) {
  const [data, setData] = useState<DashboardData | null>(null);
  const [groups, setGroups] = useState<GroupItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reloadingRuntime, setReloadingRuntime] = useState(false);
  const [privateRelays, setPrivateRelays] = useState<PrivateRelayItem[]>([]);
  const [rankRange, setRankRange] = useState<'1d' | '3d' | 'all'>('1d');

  const fetchDashboardData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.getDashboard();
      setData(res);
      const groupsRes = await api.getGroups({ limit: 100 });
      setGroups(groupsRes.items);

      // Fetch private relays for ranking calculation
      try {
        const relaysRes = await api.getPrivateRelays({ limit: 1000 });
        if (relaysRes && relaysRes.items) {
          setPrivateRelays(relaysRes.items);
        }
      } catch (err: any) {
        console.warn('Private relays API request failed.', err);
        setPrivateRelays([]);
      }
    } catch (err: any) {
      setError(err?.message || '无法加载工作台数据');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();
  }, []);

  const handleReloadRuntime = async () => {
    setReloadingRuntime(true);
    try {
      const res = await api.reloadBotRuntime();
      alert(res.detail);
      fetchDashboardData();
    } catch (err: any) {
      alert('应用运行时配置失败: ' + err.message);
    } finally {
      setReloadingRuntime(false);
    }
  };

  const handleGroupClick = (id: number | string) => {
    const normalizedId = String(id);
    setSelectedGroupId(normalizedId);
    setTab(`group-detail-${normalizedId}`);
  };

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[500px] gap-3">
        <RefreshCw className="w-8 h-8 text-indigo-600 animate-spin" />
        <p className="text-sm text-gray-500">正在载入工作台实时指标...</p>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-center flex flex-col items-center justify-center min-h-[300px] gap-2">
        <AlertTriangle className="w-10 h-10 text-red-500" />
        <p className="font-semibold text-red-700">加载失败</p>
        <p className="text-xs text-red-600">{error || '出现未知内部错误'}</p>
        <button
          onClick={fetchDashboardData}
          className="mt-4 px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold cursor-pointer"
        >
          重新尝试刷新
        </button>
      </div>
    );
  }

  const getRankedUsers = () => {
    const minTime = rankRange === '1d'
      ? Date.now() - 24 * 3600 * 1000
      : rankRange === '3d'
        ? Date.now() - 3 * 24 * 3600 * 1000
        : 0;

    const map = new Map<number, {
      telegram_user_id: number;
      first_name: string | null;
      last_name: string | null;
      username: string | null;
      total: number;
      incoming: number;
      outgoing: number;
    }>();

    for (const item of privateRelays) {
      const itemTime = new Date(item.created_at).getTime();
      if (rankRange !== 'all' && itemTime < minTime) {
        continue;
      }

      const u = item.private_user;
      if (!u) continue;

      const key = u.telegram_user_id;
      let stat = map.get(key);
      if (!stat) {
        stat = {
          telegram_user_id: key,
          first_name: u.first_name,
          last_name: u.last_name,
          username: u.username,
          total: 0,
          incoming: 0,
          outgoing: 0
        };
        map.set(key, stat);
      }

      stat.total += 1;
      if (item.direction === 'incoming') {
        stat.incoming += 1;
      } else {
        stat.outgoing += 1;
      }
    }

    return Array.from(map.values()).sort((a, b) => b.total - a.total);
  };

  const COLORS = ['#7C3AED', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#CBD5E1'];

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* Welcome status band */}
      <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="flex h-2 w-2 relative">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
            </span>
            <span className="text-[11px] font-bold text-gray-500 tracking-wider uppercase">系统就绪 (Running)</span>
          </div>
          <h1 className="text-[24px] font-semibold text-gray-900 mt-1 cursor-default">
            下午好, 管理员 ☕️
          </h1>
          <p className="text-[15px] leading-relaxed text-gray-500 mt-1">
            Telegram summary-relay 单轮询后台在线守护中。系统最后更新时间: {new Date().toLocaleTimeString()}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="text-right hidden sm:block">
            <span className="text-xs font-mono text-gray-400 block">ADMIN TOKEN IP AUTH</span>
            <span className="text-[11px] text-gray-500 font-medium">Session token active in browser</span>
          </div>
          <button
            onClick={fetchDashboardData}
            disabled={loading}
            className="p-2 border border-gray-200 hover:bg-gray-50 rounded-lg text-gray-500 hover:text-gray-900 cursor-pointer transition-colors disabled:opacity-50"
            title="刷新工作台数据"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {/* Restart request/pending banner */}
      {(data.restart_pending.length > 0 || data.bot?.needs_restart) && (
        <div className="bg-white border border-gray-200 rounded-lg p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3 shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-gray-400 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-semibold text-gray-900">配置变更挂起：需要重新加载 Bot 运行时</p>
              <p className="text-xs text-gray-500 mt-1">
                您可以选择立即应用配置到 Telegram polling 运行时。Web API 进程不会重启。
              </p>
            </div>
          </div>
          <button
            onClick={handleReloadRuntime}
            disabled={reloadingRuntime}
            className="px-4 py-2 bg-gray-900 hover:bg-gray-800 text-white rounded-lg text-xs font-semibold shrink-0 cursor-pointer shadow-xs transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {reloadingRuntime && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
            <span>重新加载 Bot 运行时</span>
          </button>
        </div>
      )}

      {/* Metric Dashboards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6 animate-in fade-in duration-300">
        {/* Bot Config Metrics */}
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_12px_28px_rgba(99,102,241,0.08)] hover:-translate-y-1 hover:border-indigo-150 transition-all duration-300 flex flex-col min-h-[142px] relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-indigo-50/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
          <div className="space-y-4 relative z-10">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-gray-400 tracking-wider uppercase">BOT 服务实例</span>
              <div className="p-2 rounded-lg bg-indigo-50/80 border border-indigo-100/60 text-indigo-600 shadow-[0_1px_3px_rgba(99,102,241,0.05)]">
                <Bot className="w-[18px] h-[18px]" />
              </div>
            </div>
            <div className="space-y-1.5">
              <h3 className="text-[17px] font-bold text-gray-850 truncate group-hover:text-indigo-600 transition-colors" title={data.bot?.name || '未配置'}>
                {data.bot ? data.bot.name : '无活跃 Bot'}
              </h3>
              <div className="flex items-center gap-2">
                <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                  data.bot?.status === 'valid'
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                    : 'bg-rose-50 text-rose-700 border border-rose-100'
                }`}>
                  {data.bot?.status === 'valid' ? '校验通过' : '待校验'}
                </span>
                <span className="inline-flex items-center gap-1 text-[11px] font-bold text-gray-400 select-none">
                  <span className={`h-1.5 w-1.5 rounded-full ${data.bot?.telegram_identity ? 'bg-emerald-500 animate-pulse' : 'bg-gray-300'}`} />
                  {data.bot?.telegram_identity ? '在线' : '离线'}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Groups total */}
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_12px_28px_rgba(59,130,246,0.08)] hover:-translate-y-1 hover:border-blue-150 transition-all duration-300 flex flex-col min-h-[142px] relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-blue-50/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
          <div className="space-y-4 relative z-10">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-gray-400 tracking-wider uppercase">已拉入群组</span>
              <div className="p-2 rounded-lg bg-blue-50/80 border border-blue-100/60 text-blue-600 shadow-[0_1px_3px_rgba(59,130,246,0.05)]">
                <Users className="w-[18px] h-[18px]" />
              </div>
            </div>
            <div className="space-y-1">
              <h3 className="text-[28px] font-extrabold text-gray-900 font-mono tracking-tight leading-none">
                {data.groups.total}
              </h3>
              <p className="text-[12px] text-gray-400 leading-none mt-1.5 flex items-center gap-1.5">
                <span>当前配置</span>
                <span className="text-blue-600 font-black bg-blue-50 px-1.5 py-0.5 rounded text-[11px] font-mono">{data.groups.enabled}</span>
                <span>个群组启用自动更新</span>
              </p>
            </div>
          </div>
        </div>

        {/* Default profile indicator */}
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_12px_28px_rgba(16,185,129,0.08)] hover:-translate-y-1 hover:border-emerald-150 transition-all duration-300 flex flex-col min-h-[142px] relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-emerald-50/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
          <div className="space-y-4 relative z-10">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-gray-400 tracking-wider uppercase">全局摘要引擎</span>
              <div className="p-2 rounded-lg bg-emerald-50/80 border border-emerald-100/60 text-emerald-600 shadow-[0_1px_3px_rgba(16,185,129,0.05)]">
                <FileText className="w-[18px] h-[18px]" />
              </div>
            </div>
            <div className="space-y-1.5">
              <h3 className="text-[17px] font-bold text-gray-850 truncate group-hover:text-emerald-600 transition-colors" title={data.default_profile?.name || '未配置'}>
                {data.default_profile ? data.default_profile.name : '未绑定模型'}
              </h3>
              <p className="text-[12px] text-gray-400 truncate leading-none mt-1">
                {data.default_profile ? `模型: ${data.default_profile.provider_name}` : '请先创建 LLM Provider'}
              </p>
            </div>
          </div>
        </div>

        {/* summary statistics */}
        <div className="bg-white rounded-xl border border-gray-100 p-6 shadow-[0_4px_20px_rgba(0,0,0,0.02)] hover:shadow-[0_12px_28px_rgba(245,158,11,0.08)] hover:-translate-y-1 hover:border-amber-150 transition-all duration-300 flex flex-col min-h-[142px] relative overflow-hidden group">
          <div className="absolute top-0 right-0 w-24 h-24 bg-gradient-to-bl from-amber-50/40 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none" />
          <div className="space-y-4 relative z-10">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-bold text-gray-400 tracking-wider uppercase">24h 摘要任务</span>
              <div className="p-2 rounded-lg bg-amber-50/80 border border-amber-100/60 text-amber-600 shadow-[0_1px_3px_rgba(245,158,11,0.05)]">
                <Workflow className="w-[18px] h-[18px]" />
              </div>
            </div>
            <div className="space-y-1">
              <h3 className="text-[28px] font-extrabold text-gray-900 font-mono tracking-tight leading-none">
                {data.summary_24h.total}
              </h3>
              <div className="flex items-center gap-2 text-[12px] mt-1.5">
                <span className="text-emerald-600 font-bold bg-emerald-50 px-1.5 py-0.5 rounded">{data.summary_24h.succeeded} 成功</span>
                <span className="text-gray-300">|</span>
                <span className="text-rose-600 font-semibold bg-rose-50 px-1.5 py-0.5 rounded">{data.summary_24h.failed} 失败</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Visual Analytics Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Trend Area Chart */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-[18px] font-semibold text-gray-900">24小时运行负荷趋势</h3>
              <p className="text-[15px] leading-relaxed text-gray-500 mt-1">每4小时自动聚合的摘要作业触发趋势图</p>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-gray-500 font-semibold">
              <TrendingUp className="w-3.5 h-3.5" />
              <span>定时任务高峰期监测</span>
            </div>
          </div>
          <div className="h-[220px] w-full pt-2">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data.summary_24h.trend} margin={{ top: 5, right: 5, left: -25, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7C3AED" stopOpacity={0.15}/>
                    <stop offset="95%" stopColor="#7C3AED" stopOpacity={0.0}/>
                  </linearGradient>
                </defs>
                <XAxis dataKey="time" stroke="#94a3b8" fontSize={11} tickLine={false} />
                <YAxis stroke="#94a3b8" fontSize={11} tickLine={false} />
                <Tooltip
                  contentStyle={{ background: '#ffffff', borderRadius: '6px', border: '1px solid #e5e7eb', fontSize: '11px', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
                />
                <Area type="monotone" dataKey="count" stroke="#7C3AED" strokeWidth={1.5} fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Group Distribution pie */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] space-y-4">
          <div>
            <h3 className="text-[18px] font-semibold text-gray-900">群组消息源活跃负荷</h3>
            <p className="text-[15px] leading-relaxed text-gray-500 mt-1">近百次摘要采样词频/消息比重分布</p>
          </div>
          <div className="h-[180px] w-full relative flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={data.summary_24h.group_distribution}
                  cx="50%"
                  cy="50%"
                  innerRadius={50}
                  outerRadius={75}
                  paddingAngle={3}
                  dataKey="value"
                >
                  {data.summary_24h.group_distribution.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{ background: '#ffffff', borderRadius: '6px', border: '1px solid #e5e7eb', fontSize: '11px', boxShadow: '0 2px 4px rgba(0,0,0,0.02)' }}
                />
              </PieChart>
            </ResponsiveContainer>
            <div className="absolute flex flex-col items-center">
              <span className="text-lg font-bold text-gray-800">{data.summary_24h.total} 次</span>
              <span className="text-[10px] text-gray-400">总分析负载</span>
            </div>
          </div>
          <div className="space-y-1.5 max-h-[100px] overflow-y-auto">
            {data.summary_24h.group_distribution.map((item, idx) => (
              <div key={item.name} className="flex items-center justify-between text-xs">
                <div className="flex items-center gap-2 truncate">
                  <span className="w-2.5 h-2.5 rounded-full block shrink-0" style={{ backgroundColor: COLORS[idx % COLORS.length] }} />
                  <span className="text-gray-600 truncate">{item.name}</span>
                </div>
                <span className="font-mono text-gray-400 font-semibold shrink-0 ml-2">{item.value}次</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Ranked Groups & Recent Audit Trail */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Ranked Private Users Message Count Table */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] lg:col-span-1 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-gray-50 pb-3">
            <div>
              <h3 className="text-[16px] font-bold text-gray-900">私聊用户消息数排行</h3>
              <p className="text-[10px] text-gray-400 mt-0.5">活跃度指标统计</p>
            </div>
            <div className="flex bg-slate-100 p-0.5 rounded-lg border border-slate-200 shrink-0">
              <button
                type="button"
                onClick={() => setRankRange('1d')}
                className={`px-2 py-1 text-[10px] font-semibold rounded-md cursor-pointer transition-all ${
                  rankRange === '1d'
                    ? 'bg-white text-indigo-600 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                1天内
              </button>
              <button
                type="button"
                onClick={() => setRankRange('3d')}
                className={`px-2 py-1 text-[10px] font-semibold rounded-md cursor-pointer transition-all ${
                  rankRange === '3d'
                    ? 'bg-white text-indigo-600 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                3天内
              </button>
              <button
                type="button"
                onClick={() => setRankRange('all')}
                className={`px-2 py-1 text-[10px] font-semibold rounded-md cursor-pointer transition-all ${
                  rankRange === 'all'
                    ? 'bg-white text-indigo-600 shadow-xs'
                    : 'text-gray-500 hover:text-gray-900'
                }`}
              >
                不限
              </button>
            </div>
          </div>

          <div className="divide-y divide-gray-100 max-h-[290px] overflow-y-auto pr-1">
            {getRankedUsers().length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 space-y-1 mt-6">
                <p>暂无此时间段内的私聊交互记录</p>
                <p className="text-[10px] text-gray-400">可调整筛选时间范围</p>
              </div>
            ) : (
              getRankedUsers().map((stat, index) => {
                const displayName = stat.first_name || stat.last_name
                  ? `${stat.first_name || ''} ${stat.last_name || ''}`.trim()
                  : `@${stat.username || stat.telegram_user_id}`;
                return (
                  <div key={stat.telegram_user_id} className="py-2.5 flex items-center justify-between gap-3 text-xs text-slate-700">
                    <div className="flex items-center gap-2.5 min-w-0">
                      {/* Ranking badge/bubble */}
                      <span className={`w-4 text-center font-bold text-[10px] font-mono shrink-0 select-none ${
                        index === 0 ? 'text-indigo-600' : index === 1 ? 'text-indigo-400' : 'text-gray-300'
                      }`}>
                        {index + 1}
                      </span>
                      {/* User Avatar */}
                      <div className="w-8 h-8 rounded-full bg-slate-50 border border-slate-100 flex items-center justify-center font-bold text-gray-700 shrink-0">
                        {stat.first_name ? stat.first_name[0].toUpperCase() : 'U'}
                      </div>
                      <div className="truncate space-y-0.5 min-w-0">
                        <p className="font-bold text-gray-800 truncate" title={displayName}>{displayName}</p>
                      <p className="text-[10px] text-gray-400 font-mono">
                          ID: {stat.telegram_user_id}
                        </p>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 shrink-0">
                      <div className="text-right">
                        <span className="font-bold font-mono text-gray-900 block leading-none">{stat.total}</span>
                        <span className="text-[8px] text-gray-400 font-medium font-mono">
                          {stat.incoming}↓ / {stat.outgoing}↑
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        {/* Recent Audit action timeline */}
        <div className="bg-white rounded-lg border border-gray-200 p-5 shadow-[0_1px_2px_rgba(0,0,0,0.03)] lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-[18px] font-semibold text-gray-900">今日审计流 (Recent Actions)</h3>
            <button
              onClick={() => setTab('audit-logs')}
              className="text-xs text-gray-500 hover:text-gray-900 hover:underline font-semibold"
            >
              完整审计链表 &rarr;
            </button>
          </div>

          <div className="space-y-4 max-h-[280px] overflow-y-auto">
            {data.recent_audit_logs.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-6">暂无审计日志</p>
            ) : (
              data.recent_audit_logs.map((log) => (
                <div key={log.id} className="flex gap-3 text-xs leading-none">
                  <div className="flex flex-col items-center shrink-0">
                    <div className={`w-6 h-6 rounded-full flex items-center justify-center text-white font-extrabold text-[10px] select-none shadow-[0_1.5px_4px_rgba(0,0,0,0.08)] ${
                      log.actor === 'admin'
                        ? 'bg-gradient-to-tr from-indigo-500 to-purple-500'
                        : 'bg-gradient-to-tr from-emerald-500 to-teal-500'
                    }`}>
                      {log.actor === 'admin' ? 'A' : 'SYS'}
                    </div>
                    <div className="w-px flex-1 bg-gray-100 mt-2"></div>
                  </div>
                  <div className="flex-1 space-y-1 pb-3">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-gray-800">
                        {log.actor === 'admin' ? '操作员: admin' : '系统内核 (daemon)'}
                      </span>
                      <span className="text-[10px] text-gray-400">
                        {new Date(log.created_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <p className="text-gray-600 leading-normal">
                      执行了 <span className="font-mono bg-gray-100 text-gray-700 px-1 border border-gray-200/50 rounded-sm">{log.action}</span> 事务对
                      <strong className="text-gray-800 font-medium"> ({log.entity_type})</strong>.
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
