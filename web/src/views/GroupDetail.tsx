import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/client';
import { GroupDetail as GroupDetailType, SummaryProfile, SummaryJob } from '../api/types';
import CustomSelect from '../components/CustomSelect';
import {
  ArrowLeft,
  RefreshCw,
  Play,
  Settings,
  History,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Clock,
  Cpu,
  Timer,
  Globe,
  Loader2,
  Lock
} from 'lucide-react';
import { useToast } from '../components/Toast';

interface GroupDetailViewProps {
  groupId: string;
  onBack: () => void;
}

export default function GroupDetail({ groupId, onBack }: GroupDetailViewProps) {
  const showToast = useToast();
  const navigate = useNavigate();
  const [data, setData] = useState<GroupDetailType | null>(null);
  const [profiles, setProfiles] = useState<SummaryProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorHeader, setErrorHeader] = useState<string | null>(null);

  // Form Fields
  const [formEnabled, setFormEnabled] = useState(false);
  const [formInterval, setFormInterval] = useState(180);
  const [formTimezone, setFormTimezone] = useState('Asia/Shanghai');
  const [formProfileId, setFormProfileId] = useState<string>(''); // empty matches default fallback
  const [savingSettings, setSavingSettings] = useState(false);

  // Manual trigger states
  const [triggeringJob, setTriggeringJob] = useState(false);
  const [pollingStatus, setPollingStatus] = useState<string | null>(null);
  const pollIntervalRef = useRef<any>(null);

  const fetchGroupDetail = async () => {
    try {
      const detail = await api.getGroupDetail(groupId);
      setData(detail);

      // Bind initial edit fields
      setFormEnabled(detail.settings.enabled);
      setFormInterval(detail.settings.interval_minutes);
      setFormTimezone(detail.settings.timezone);
      setFormProfileId(detail.settings.summary_profile_id ? String(detail.settings.summary_profile_id) : '');

      // Load profile select
      const profs = await api.getProfiles();
      setProfiles(profs);

      // If there is an active job in detail upon loading, start polling it
      if (detail.active_job) {
        startPollingJob(`/api/groups/${groupId}/summary-jobs/${detail.active_job.id}`);
      }
    } catch (err: any) {
      setErrorHeader(err.message || '获取群组特化详情发生了错误');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGroupDetail();
    return () => {
      if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);
    };
  }, [groupId]);

  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSavingSettings(true);
    try {
      const updated = {
        enabled: formEnabled,
        interval_minutes: formInterval,
        summary_profile_id: formProfileId ? Number(formProfileId) : null,
        timezone: formTimezone
      };
      await api.updateGroupSettings(groupId, updated);
      showToast({
        tone: 'success',
        title: '群组设置已保存'
      });
      fetchGroupDetail();
    } catch (err: any) {
      showToast({
        tone: 'error',
        title: '保存设置失败',
        detail: err.message
      });
    } finally {
      setSavingSettings(false);
    }
  };

  const handleTriggerSummary = async () => {
    if (triggeringJob || data?.active_job) return;
    setTriggeringJob(true);
    setPollingStatus('调度中 (Accepted)...');
    try {
      const res = await api.triggerGroupSummary(groupId);
      // start real-time polling loop
      startPollingJob(res.poll_url);
    } catch (err: any) {
      showToast({
        tone: 'error',
        title: '手动摘要触发失败',
        detail: err.message
      });
      setTriggeringJob(false);
      setPollingStatus(null);
    }
  };

  const startPollingJob = (pollUrl: string) => {
    if (pollIntervalRef.current) clearInterval(pollIntervalRef.current);

    setTriggeringJob(true);

    pollIntervalRef.current = setInterval(async () => {
      try {
        const job = await api.pollJob(pollUrl);
        setPollingStatus(`生成中 (Status: ${job.status})...`);

        if (job.status === 'succeeded' || job.status === 'failed' || job.status === 'blocked') {
          clearInterval(pollIntervalRef.current);
          pollIntervalRef.current = null;
          setTriggeringJob(false);
          setPollingStatus(null);

          if (job.status === 'succeeded') {
            showToast({
              tone: 'success',
              title: '群聊纪要已生成',
              detail: '摘要已成功投递进群。'
            });
          } else {
            showToast({
              tone: 'error',
              title: `大模型处理已中止${job.error_type ? `: ${job.error_type}` : ''}`,
              detail: job.error_message || '未知内部错误'
            });
          }
          fetchGroupDetail(); // Refresh logs and stats
        }
      } catch (err) {
        // fail silently or stop polling on fatal
        clearInterval(pollIntervalRef.current);
        pollIntervalRef.current = null;
        setTriggeringJob(false);
        setPollingStatus(null);
      }
    }, 2000);
  };

  if (loading && !data) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-2">
        <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin" />
        <p className="text-sm text-gray-500">正在获取群组特化参数链表...</p>
      </div>
    );
  }

  if (errorHeader || !data) {
    return (
      <div className="p-6 bg-red-50 border border-red-200 rounded-xl text-center space-y-4 max-w-lg mx-auto mt-12">
        <AlertTriangle className="w-10 h-10 text-red-500 mx-auto" />
        <div className="space-y-1">
          <p className="font-semibold text-red-700">加载失败</p>
          <p className="text-xs text-red-600">{errorHeader}</p>
        </div>
        <button
          onClick={onBack}
          className="px-4 py-1.5 bg-red-600 hover:bg-red-700 text-white rounded text-xs font-semibold"
        >
          返回群组名录
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* Detail object Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-1.5 border border-[#e4e6ec] bg-white rounded-lg text-gray-500 hover:text-indigo-600 hover:bg-gray-50 cursor-pointer"
            title="返回群组面板"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-[24px] font-bold text-gray-900 truncate max-w-[280px]" title={data.title || `群组 ${data.chat_id}`}>
                {data.title || `群组 ${data.chat_id}`}
              </h2>
              <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                data.settings.enabled
                  ? 'bg-green-50 text-green-700'
                   : 'bg-gray-100 text-gray-500'
              }`}>
                {data.settings.enabled ? '自动汇总中' : '已休眠'}
              </span>
            </div>
            <p className="text-xs text-gray-400 mt-1">ID: {data.chat_id} | 发现契机: {new Date(data.discovered_at).toLocaleDateString()}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 w-full sm:w-auto justify-end">
          <button
            onClick={fetchGroupDetail}
            className="p-2 border border-[#e4e6ec] bg-white hover:bg-gray-50 rounded-lg text-gray-500 hover:text-indigo-600"
            title="刷新详情数据"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {/* Manual Trigger button */}
          <button
            onClick={handleTriggerSummary}
            disabled={triggeringJob || !!data.active_job}
            className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed shadow-sm shrink-0"
          >
            {triggeringJob ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
            <span>立即生成当前摘要</span>
          </button>
        </div>
      </div>

      {/* Warning banner if another summary job in-flight */}
      {(data.active_job || triggeringJob) && (
        <div className="bg-blue-50 border border-blue-200 text-blue-800 rounded-xl p-4 flex gap-3 animate-pulse">
          <Loader2 className="w-5 h-5 text-blue-500 shrink-0 mt-0.5 animate-spin" />
          <div className="text-xs leading-relaxed">
            <p className="font-bold text-blue-900">该群有摘要正在生成，暂不能重复触发。</p>
            <p className="text-blue-700 mt-0.5">
              系统当前正在检索最新消息、进行分级汇编并发布推送大纲。... <strong>当前轮询进度: {pollingStatus || '编译模型上下文'}</strong>
            </p>
          </div>
        </div>
      )}

      {/* 2-Column Grid for forms and status layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Settings Panel form */}
        <div className="lg:col-span-8 bg-white border border-[#e4e6ec] rounded-xl shadow-sm overflow-hidden">
          <div className="px-6 py-4 border-b border-[#e4e6ec] bg-[#fbfbfe]">
            <h3 className="text-sm font-bold text-gray-900">定时排程与提示词模板绑定</h3>
          </div>

          <form onSubmit={handleSaveSettings} className="p-6 space-y-6">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {/* Cron minutes selection */}
              <div className="space-y-1.5 z-20">
                <label className="text-xs font-semibold text-gray-700 block">自动汇总间隔时间</label>
                <CustomSelect
                  options={[
                    { value: "60", label: "1 小时" },
                    { value: "180", label: "3 小时" },
                    { value: "360", label: "6 小时" },
                    { value: "720", label: "12 小时" },
                    { value: "1440", label: "24 小时" },
                  ]}
                  value={formInterval.toString()}
                  onChange={(val) => setFormInterval(parseInt(val) || 180)}
                />
              </div>

              {/* Timezone Selection */}
              <div className="space-y-1.5 z-20">
                <label className="text-xs font-semibold text-gray-700 block">时区</label>
                <CustomSelect
                  options={[
                    { value: "Asia/Shanghai", label: "上海时间" },
                    { value: "Asia/Tokyo", label: "东京时间" },
                    { value: "UTC", label: "UTC 零时区" },
                    { value: "America/New_York", label: "纽约时间" },
                  ]}
                  value={formTimezone}
                  onChange={(val) => setFormTimezone(val)}
                />
              </div>
            </div>

            {/* Profile Selection list override */}
            <div className="space-y-1.5 z-10">
              <label className="text-xs font-semibold text-gray-700 block">专属提示词模板绑定</label>
              <CustomSelect
                options={[
                  { value: "", label: "继承全局默认策略" },
                  ...profiles.map(p => ({
                    value: String(p.id),
                    label: `${p.name}${p.is_default ? ' (默认)' : ''}`
                  }))
                ]}
                value={formProfileId}
                onChange={(val) => setFormProfileId(val)}
                searchable={profiles.length > 5}
              />
            </div>

            {/* Switch option */}
            <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
              <div className="space-y-0.5">
                <span className="text-xs font-semibold text-gray-800 block">开启自动生成的群组自动轮询</span>
              </div>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={formEnabled}
                  onChange={(e) => setFormEnabled(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
              </label>
            </div>

            {/* Save Buttons */}
            <div className="pt-4 border-t border-gray-100 flex justify-end gap-2">
              <button
                type="submit"
                disabled={savingSettings}
                className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg shadow-sm disabled:opacity-50 inline-flex items-center gap-1 cursor-pointer"
              >
                {savingSettings && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
                <span>保存设置</span>
              </button>
            </div>
          </form>
        </div>

        {/* Status card right side */}
        <div className="lg:col-span-4 space-y-6">
          <div className="bg-white border border-[#e4e6ec] rounded-xl shadow-sm overflow-hidden">
            <div className="px-5 py-4 border-b border-[#e4e6ec] bg-[#fbfbfe]">
              <h3 className="text-xs font-bold text-gray-900">群组运行核心状态指标</h3>
            </div>
            <div className="p-5 space-y-4 text-xs">
              <div className="flex items-center justify-between">
                <span className="text-gray-500">时空位置</span>
                <span className="font-mono text-gray-800 font-bold flex items-center gap-1">
                  <Globe className="w-3.5 h-3.5 text-gray-400" />
                  {data.settings.timezone}
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-gray-500">自动周期</span>
                <span className="font-mono text-gray-800 font-bold flex items-center gap-1">
                  <Timer className="w-3.5 h-3.5 text-gray-400" />
                  每 {data.settings.interval_minutes / 60} 小时一发
                </span>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-gray-500">实际生效提示词模板</span>
                <span className="text-indigo-600 font-bold truncate max-w-[155px]" title={data.effective_profile?.name}>
                  {data.effective_profile?.name || '无'}
                </span>
              </div>

              <div className="border-t border-gray-100 my-2"></div>

              <div className="space-y-1.5">
                <span className="text-[10px] text-gray-400 uppercase tracking-widest block font-bold">上次整理点及成果</span>
                <div className="bg-[#fafafa] p-3 border border-[#e4e6ec] rounded-lg space-y-1.5 text-[11px]">
                  <div className="flex justify-between">
                    <span className="text-gray-500">截止消息流水序列</span>
                    <strong className="text-gray-700 font-mono">#{data.summary_state?.last_summary_sequence || 0}</strong>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500">发送完毕时间</span>
                    <strong className="text-gray-700 font-mono">
                      {data.summary_state?.last_summary_at ? new Date(data.summary_state.last_summary_at).toLocaleTimeString() : '尚未启动'}
                    </strong>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

    </div>
  );
}
