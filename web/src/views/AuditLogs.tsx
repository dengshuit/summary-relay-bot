import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { AuditLog } from '../api/types';
import {
  History,
  Search,
  ShieldAlert,
  User,
  ChevronDown,
  ChevronUp,
  Calendar,
  Filter,
  RefreshCw,
  FolderOpen,
  X
} from 'lucide-react';
import DateRangePicker from '../components/DateRangePicker';
import CustomSelect from '../components/CustomSelect';

export default function AuditLogs() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  // Filter States
  const [entityType, setEntityType] = useState('');
  const [actionSearch, setActionSearch] = useState('');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');

  // Expandable row IDs
  const [expandedLogIds, setExpandedLogIds] = useState<Record<string, boolean>>({});

  const fetchLogs = async () => {
    setLoading(true);
    setErrorText(null);
    try {
      const res = await api.getAuditLogs({
        entity_type: entityType || undefined,
        action: actionSearch || undefined,
        from: fromDate ? new Date(fromDate).toISOString() : undefined,
        to: toDate ? new Date(toDate).toISOString() : undefined
      });
      setLogs(res.items);
    } catch (err: any) {
      setErrorText(err.message || '获取审计日志遭到网络断开');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
  }, [entityType, actionSearch, fromDate, toDate]);

  const toggleExpandLog = (id: number) => {
    setExpandedLogIds(prev => ({
      ...prev,
      [id]: !prev[id]
    }));
  };

  const getLogExplanation = (log: AuditLog) => {
    switch (log.action) {
      case 'create':
        return `创建了新 ${log.entity_type} 实体`;
      case 'update':
        return `修改更新了 ${log.entity_type} 实体属性`;
      case 'delete':
        return `永久删除了 ${log.entity_type} 配置`;
      case 'validate_success':
        return `校验 Telegram Bot 双向通信连接成功`;
      case 'validate_failure':
        return `测试 API 验证联通失败`;
      case 'update_summary_settings':
        return `更改修改了 Telegram 群组汇总调度策略`;
      case 'manual_summary_success':
        return `管理员强制对群组触发单次手动汇总处理成功`;
      case 'set_default':
        return `将当前 ${log.entity_type} 划设为系统默认处理模板`;
      case 'polling_worker_restart':
        return `重新启动了后台轮询守护主核心引擎机制`;
      default:
        return `执行了 "${log.action}" 事务`;
    }
  };

  const tryPrettyPrintJSON = (value: Record<string, unknown> | null) => {
    if (!value) return '空 (None)';
    return JSON.stringify(value, null, 2);
  };

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* Title Header */}
      <div className="flex justify-between items-center animate-in fade-in slide-in-from-top-4 duration-200">
        <div>
          <h2 className="text-[24px] font-semibold text-gray-900 leading-none">审计日志</h2>
        </div>
      </div>

      {/* Structured Filter Card */}
      <div className="bg-white rounded-xl border border-[#e4e6ec] p-4 shadow-sm grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 items-center">
        {/* entity type select */}
        <div className="z-20">
          <CustomSelect
            options={[
              { value: "", label: "全部类别" },
              { value: "bot", label: "机器人配置" },
              { value: "llm_provider", label: "提供商连接" },
              { value: "summary_profile", label: "摘要模版" },
              { value: "group", label: "群组设置" },
              { value: "system", label: "系统守护" }
            ]}
            value={entityType}
            onChange={(val) => setEntityType(val)}
            placeholder="筛选实体类别"
          />
        </div>

        {/* action search */}
        <div className="relative">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-gray-400 pointer-events-none">
            <Search className="w-3.5 h-3.5" />
          </span>
          <input
            type="text"
            placeholder="搜索事务动作 (e.g. create, update)"
            value={actionSearch}
            onChange={(e) => setActionSearch(e.target.value)}
            className="w-full h-10 pl-9 pr-4 py-2 bg-white border border-[#e4e6ec] rounded-lg text-[15px] text-gray-800 placeholder-gray-400 focus:border-indigo-500 focus:outline-none leading-normal transition-all"
          />
        </div>

        {/* Custom Range Selector spanning 2 grid columns on large screens */}
        <div className="lg:col-span-2 flex lg:justify-end">
          <DateRangePicker
            fromDate={fromDate}
            toDate={toDate}
            onChange={(from, to) => {
              setFromDate(from);
              setToDate(to);
            }}
          />
        </div>
      </div>

      {/* Main Timeline content wrapper */}
      <div className="bg-white border border-[#e4e6ec] rounded-xl shadow-sm p-6 overflow-hidden">
        {loading && logs.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 gap-2">
            <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin" />
            <p className="text-xs text-gray-400">拉取系统日志中...</p>
          </div>
        ) : errorText ? (
          <p className="text-xs text-red-500 text-center py-6">加载日志遇到异常: {errorText}</p>
        ) : logs.length === 0 ? (
          <div className="text-center py-12 space-y-3">
            <FolderOpen className="w-10 h-10 text-slate-300 mx-auto" />
            <p className="text-xs text-gray-400 font-semibold">暂无任何在案匹配的审计日志记录点</p>
          </div>
        ) : (
          <div className="relative border-l border-indigo-100 ml-3 space-y-6">
            {logs.map((log) => {
              const isExpanded = !!expandedLogIds[log.id];
              return (
                <div key={log.id} className="relative pl-6 group">
                  {/* Circular visual dot on borderline */}
                  <span className={`absolute -left-3 top-1 flex h-6 w-6 items-center justify-center rounded-full text-white font-extrabold text-[10px] select-none hover:scale-110 shadow-xs transition-transform ${
                    log.actor === 'admin'
                      ? 'bg-gradient-to-tr from-indigo-500 to-purple-500'
                      : 'bg-gradient-to-tr from-emerald-500 to-teal-500'
                  }`}>
                    {log.actor === 'admin' ? 'A' : 'SYS'}
                  </span>

                  {/* Log core contents */}
                  <div className="space-y-1.5 leading-none">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <span className="font-bold text-gray-900 text-xs">
                          {log.actor === 'admin' ? '操作员 (admin admin)' : '系统调度 (polling daemon)'}
                        </span>
                        <span className="text-slate-300">|</span>
                        <span className="px-1.5 py-0.5 rounded text-[8px] font-bold font-mono uppercase bg-slate-100 text-slate-500">
                          {log.action}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          实体: <code className="bg-gray-50 border border-gray-100 rounded px-1 font-bold text-indigo-600">{log.entity_type}</code>
                        </span>
                        {log.entity_id && (
                          <span className="text-[10px] font-mono text-gray-400">
                            (ID: {log.entity_id})
                          </span>
                        )}
                      </div>

                      <span className="text-[10px] font-mono text-gray-400">
                        {new Date(log.created_at).toLocaleString()}
                      </span>
                    </div>

                    {/* Explanatory description card */}
                    <div className="bg-[#fbfbfe]/70 hover:bg-[#fbfbfe] border border-gray-100 p-3 rounded-lg flex items-center justify-between gap-4 cursor-pointer" onClick={() => toggleExpandLog(log.id)}>
                      <p className="text-[14px] text-gray-700 leading-normal">
                        💁 {getLogExplanation(log)}。
                      </p>
                      <button className="text-gray-400 hover:text-indigo-600 text-[11px] font-semibold flex items-center gap-0.5 shrink-0 select-none">
                        <span>详情比较</span>
                        {isExpanded ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>

                    {/* Side-by-side JSON panels comparisons */}
                    {isExpanded && (
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pt-2 animate-fadeIn">
                        {/* Before panel */}
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold text-gray-400 uppercase tracking-widest pl-1 block">变动前状态 (Before Props)</span>
                          <pre className="bg-[#fafafa] border border-gray-150 p-3 rounded-lg font-mono text-[10px] text-gray-500 leading-relaxed overflow-x-auto max-h-[180px] block">
                            {tryPrettyPrintJSON(log.redacted_before)}
                          </pre>
                        </div>

                        {/* After panel */}
                        <div className="space-y-1">
                          <span className="text-[10px] font-bold text-indigo-500 uppercase tracking-widest pl-1 block">变动后成果 (After Props)</span>
                          <pre className="bg-indigo-50/20 border border-indigo-100 p-3 rounded-lg font-mono text-[10px] text-gray-600 leading-relaxed overflow-x-auto max-h-[180px] block">
                            {tryPrettyPrintJSON(log.redacted_after)}
                          </pre>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

function WorkflowIcon(props: any) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      {...props}
    >
      <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
    </svg>
  );
}
