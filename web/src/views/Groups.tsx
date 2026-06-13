import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { GroupItem, SummaryProfile, HistoricalSummary } from '../api/types';
import {
  Users,
  Search,
  Filter,
  ChevronRight,
  Info,
  ToggleLeft,
  ToggleRight,
  RefreshCw,
  XCircle,
  CheckCircle,
  HelpCircle,
  AlertTriangle,
  Clock,
  Eye,
  X,
  FileText,
  Check,
  Calendar
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import CustomSelect from '../components/CustomSelect';
import { useToast } from '../components/Toast';

interface GroupsProps {
  setTab: (tab: string) => void;
  setSelectedGroupId: (id: string | null) => void;
}

export default function Groups({ setTab, setSelectedGroupId }: GroupsProps) {
  const showToast = useToast();
  const [items, setItems] = useState<GroupItem[]>([]);
  const [profiles, setProfiles] = useState<SummaryProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorHeader, setErrorHeader] = useState<string | null>(null);

  // Filter States
  const [searchText, setSearchText] = useState('');
  const [filterEnabled, setFilterEnabled] = useState<string>(''); // '' or 'true' or 'false'
  const [filterProfileId, setFilterProfileId] = useState('');
  const [filterStatus, setFilterStatus] = useState('');

  // Pagination cursor
  const [nextCursor, setNextCursor] = useState<string | null>(null);

  // Group summaries view states
  const [viewingGroup, setViewingGroup] = useState<GroupItem | null>(null);
  const [groupSummaries, setGroupSummaries] = useState<HistoricalSummary[]>([]);
  const [loadingSummaries, setLoadingSummaries] = useState(false);
  const [summariesError, setSummariesError] = useState<string | null>(null);
  const [selectedSummary, setSelectedSummary] = useState<HistoricalSummary | null>(null);

  const handleShowGroupSummaries = async (group: GroupItem) => {
    setViewingGroup(group);
    setLoadingSummaries(true);
    setSummariesError(null);
    try {
      const res = await api.getSummaries({ group_id: group.id });
      setGroupSummaries(res.items);
    } catch (err: any) {
      setSummariesError(err.message || '获取该群组的历史总结成果失败');
    } finally {
      setLoadingSummaries(false);
    }
  };

  const fetchGroups = async () => {
    setLoading(true);
    setErrorHeader(null);
    try {
      const res = await api.getGroups({
        q: searchText,
        enabled: filterEnabled === '' ? undefined : filterEnabled === 'true',
        profile_id: filterProfileId || undefined,
        status: filterStatus || undefined
      });
      setItems(res.items);
      setNextCursor(res.next_cursor);

      // Grab profiles for select dropdown matches
      const profs = await api.getProfiles();
      setProfiles(profs);
    } catch (err: any) {
      setErrorHeader(err.message || '加载群组列表发生致命阻断');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchGroups();
  }, [searchText, filterEnabled, filterProfileId, filterStatus]);

  const handleToggleGroup = async (groupId: number | string, currentEnabled: boolean) => {
    try {
      // Find the group and grab details or settings
      const found = items.find(g => String(g.id) === String(groupId));
      if (!found) return;

      const updatedSettings = {
        ...found.settings,
        enabled: !currentEnabled
      };

      await api.updateGroupSettings(groupId, updatedSettings);
      fetchGroups();
    } catch (err: any) {
      showToast({
        tone: 'error',
        title: '更改群组启用态失败',
        detail: err.message
      });
    }
  };

  const navigateToDetail = (id: number | string) => {
    const normalizedId = String(id);
    setSelectedGroupId(normalizedId);
    setTab(`group-detail-${normalizedId}`);
  };

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* View Title Header */}
      <div className="flex justify-between items-center animate-in fade-in slide-in-from-top-4 duration-200">
        <div>
          <h2 className="text-[24px] font-semibold text-gray-900 leading-none">群组管理</h2>
        </div>
        <button
          onClick={fetchGroups}
          className="p-2 border border-gray-200 hover:bg-gray-100 rounded-lg text-gray-400 hover:text-indigo-600 cursor-pointer h-10 w-10 flex items-center justify-center transition-all"
          title="重新载入群组数据"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Structured Filter center card */}
      <div className="bg-white rounded-xl border border-[#e4e6ec] p-4 shadow-sm grid grid-cols-1 md:grid-cols-4 gap-3">
        {/* Search Input Q */}
        <div className="relative">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-gray-400 pointer-events-none">
            <Search className="w-4 h-4" />
          </span>
          <input
            type="text"
            placeholder="搜索群组标题/ID/用户名"
            value={searchText}
            onChange={(e) => setSearchText(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-[15px] text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-indigo-500 h-10 leading-normal"
          />
        </div>

        {/* Filter Enabled */}
        <div className="w-full sm:w-48 z-40">
          <CustomSelect
            options={[
              { value: "", label: "全部推送模式" },
              { value: "true", label: "开启自动生成" },
              { value: "false", label: "关闭自动生成" },
            ]}
            value={filterEnabled}
            onChange={(val) => setFilterEnabled(val)}
            placeholder="筛选推送模式"
          />
        </div>

        {/* Filter Profile Override */}
        <div className="w-full sm:w-56 z-30">
          <CustomSelect
            options={[
              { value: "", label: "全部绑定 Profile" },
              ...profiles.map(p => ({
                value: String(p.id),
                label: `${p.name}${p.is_default ? ' (默认)' : ''}`
              }))
            ]}
            value={filterProfileId}
            onChange={(val) => setFilterProfileId(val)}
            placeholder="筛选绑定 Profile"
            searchable={profiles.length > 5}
          />
        </div>

        {/* Filter Last Run status */}
        <div className="w-full sm:w-48 z-20">
          <CustomSelect
            options={[
              { value: "", label: "全部摘要状态" },
              { value: "succeeded", label: "生成成功" },
              { value: "failed", label: "生成失败" },
              { value: "running", label: "正在生成" },
              { value: "blocked", label: "已受限" },
            ]}
            value={filterStatus}
            onChange={(val) => setFilterStatus(val)}
            placeholder="筛选摘要状态"
          />
        </div>
      </div>

      {/* Main Table area */}
      <div className="bg-white border border-[#e4e6ec] rounded-xl shadow-sm overflow-hidden">
        {items.length === 0 ? (
          <div className="p-12 text-center flex flex-col items-center justify-center space-y-3">
            <Users className="w-12 h-12 text-gray-300" />
            <div className="space-y-1">
              <p className="text-sm font-semibold text-gray-800">
                {searchText || filterEnabled || filterProfileId || filterStatus
                  ? '未筛选到匹配的群组'
                  : '尚无自动拉入登记的群组'
                }
              </p>
              <p className="text-xs text-gray-400 max-w-sm leading-normal">
                把 summary-relay Bot 邀请入群并给予消息查看权限，群内产生新聊天后此处会自动发现呈现群组。
              </p>
            </div>
            {(searchText || filterEnabled || filterProfileId || filterStatus) && (
              <button
                onClick={() => {
                  setSearchText('');
                  setFilterEnabled('');
                  setFilterProfileId('');
                  setFilterStatus('');
                }}
                className="px-3 py-1 bg-indigo-50 text-indigo-600 hover:bg-indigo-100 rounded text-xs font-semibold"
              >
                重置过滤器
              </button>
            )}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-[#e4e6ec] text-[12px] font-bold text-gray-500 uppercase tracking-wider select-none h-12">
                  <th className="px-6 py-3">群组基础属性</th>
                  <th className="px-4 py-3">汇总开关</th>
                  <th className="px-4 py-3">默认调度周期</th>
                  <th className="px-4 py-3">提示词模板</th>
                  <th className="px-4 py-3">上次汇总校验</th>
                  <th className="px-6 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 text-[14px]">
                {items.map((g) => {
                  // Format interval
                  const hours = g.settings.interval_minutes / 60;
                  const intStr = hours >= 1 ? `${hours.toFixed(1)}小时/次` : `${g.settings.interval_minutes}分钟/次`;

                  // Format dates
                  const discDate = new Date(g.discovered_at).toLocaleDateString();

                  return (
                    <tr
                      key={g.id}
                      className={`hover:bg-[#fbfbfd] transition-colors h-14 ${
                        g.settings.enabled ? 'text-gray-800' : 'text-gray-400 bg-gray-50/20'
                      }`}
                    >
                      {/* Name, username, metadata */}
                      <td className="px-6 py-3">
                        <div className="flex flex-col gap-0.5">
                          <span className="font-semibold text-gray-950 text-[14px] truncate max-w-[220px]">
                            {g.title || `群组 ${g.chat_id}`}
                          </span>
                          <div className="flex items-center gap-2 text-[12px] text-gray-400 font-mono mt-0.5">
                            <span>ID: {g.chat_id}</span>
                            {g.username && (
                              <span className="text-gray-500">@{g.username}</span>
                            )}
                          </div>
                        </div>
                      </td>

                      {/* Push switch toggle */}
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <label className="relative inline-flex items-center cursor-pointer select-none">
                            <input
                              type="checkbox"
                              checked={g.settings.enabled}
                              onChange={() => handleToggleGroup(g.id, g.settings.enabled)}
                              className="sr-only peer"
                            />
                            <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                          </label>
                          <span className={`text-[12px] font-medium leading-none ${g.settings.enabled ? 'text-gray-800' : 'text-gray-400'}`}>
                            {g.settings.enabled ? '已启用' : '已睡眠'}
                          </span>
                        </div>
                      </td>

                      {/* Interval settings */}
                      <td className="px-4 py-3 font-medium font-mono text-gray-700">
                        {intStr}
                      </td>

                      {/* Profile Name mapping */}
                      <td className="px-4 py-3 max-w-[180px] truncate">
                        {g.effective_profile ? (
                          <span className="font-semibold text-gray-800 truncate" title={g.effective_profile.name}>{g.effective_profile.name}</span>
                        ) : (
                          <span className="text-gray-400 italic">缺省默认模板</span>
                        )}
                      </td>

                      {/* Last run summary status */}
                      <td className="px-4 py-3">
                        {g.last_summary ? (
                          <div className="flex flex-col gap-0.5 max-w-[150px]">
                            <div className="flex items-center">
                              {g.last_summary.status === 'succeeded' ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-150 shrink-0 select-none">
                                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
                                  成功
                                </span>
                              ) : g.last_summary.status === 'failed' ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-rose-50 text-rose-700 border border-rose-250 shrink-0 select-none">
                                  <span className="w-1.5 h-1.5 rounded-full bg-rose-500" />
                                  失败
                                </span>
                              ) : g.last_summary.status === 'blocked' ? (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-50 text-amber-700 border border-amber-200 shrink-0 select-none">
                                  <span className="w-1.5 h-1.5 rounded-full bg-amber-500" />
                                  风控
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-700 border border-blue-150 shrink-0 select-none">
                                  <span className="w-1.5 h-1.5 rounded-full bg-blue-500 animate-pulse" />
                                  编制中
                                </span>
                              )}
                            </div>
                            <span className="text-[9px] text-gray-400 font-mono mt-1 ml-1">
                              {g.last_summary.finished_at ? new Date(g.last_summary.finished_at).toLocaleTimeString() : '未见记录'}
                            </span>
                          </div>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-gray-50 text-gray-500 border border-gray-200 shrink-0 select-none">
                            <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                            未运行
                          </span>
                        )}
                      </td>

                      {/* Action trigger edit */}
                      <td className="px-6 py-3 text-right">
                        <div className="flex items-center justify-end gap-2 text-xs">
                          <button
                            onClick={() => handleShowGroupSummaries(g)}
                            className="px-2.5 py-1.5 font-semibold text-indigo-600 hover:text-indigo-800 bg-indigo-50/50 hover:bg-indigo-50 border border-indigo-100/80 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1 shrink-0"
                          >
                            <Eye className="w-3.5 h-3.5" />
                            <span>查看</span>
                          </button>
                          <div className="h-4 w-px bg-gray-200" />
                          <button
                            onClick={() => navigateToDetail(g.id)}
                            className="px-2.5 py-1.5 font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 active:scale-95 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1 shrink-0"
                          >
                            <span>编辑</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 历史总结记录列表弹窗 */}
      <AnimatePresence>
        {viewingGroup && (
          <div
            className="fixed inset-0 bg-black/45 backdrop-blur-xs flex items-center justify-center z-50 p-4 animate-in fade-in duration-150"
            onClick={() => setViewingGroup(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-2xl bg-white rounded-xl border border-gray-205 shadow-xl overflow-hidden flex flex-col max-h-[80vh]"
            >
              {/* Header */}
              <div className="px-6 py-4 border-b border-gray-200 bg-[#fbfbfe] flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-indigo-50/70 border border-indigo-100 text-indigo-600 rounded-lg shrink-0">
                    <FileText className="w-4.5 h-4.5 shrink-0" />
                  </div>
                  <div className="min-w-0">
                    <h3 className="font-bold text-gray-900 text-[15px] truncate max-w-[400px]">
                      【{viewingGroup.title || `群组 ${viewingGroup.chat_id}`}】历史总结
                    </h3>
                    <p className="text-[10px] text-gray-400 font-mono mt-0.5">
                      群组 ID: {viewingGroup.chat_id} {viewingGroup.username && `| @${viewingGroup.username}`}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => setViewingGroup(null)}
                  className="p-1.5 px-2 bg-white text-xs border border-gray-200 hover:bg-slate-50 cursor-pointer hover:border-gray-300 text-gray-400 hover:text-gray-650 rounded-lg transition-all"
                >
                  <X className="w-4.5 h-4.5" />
                </button>
              </div>

              {/* Body */}
              <div className="p-6 overflow-y-auto flex-1 bg-white">
                {loadingSummaries ? (
                  <div className="p-12 flex flex-col items-center justify-center gap-3">
                    <RefreshCw className="w-7 h-7 text-indigo-500 animate-spin" />
                    <span className="text-xs text-gray-400 font-medium">加载历史归档记录...</span>
                  </div>
                ) : summariesError ? (
                  <div className="p-8 text-center text-xs text-rose-500 leading-relaxed font-semibold">
                    {summariesError}
                  </div>
                ) : groupSummaries.length === 0 ? (
                  <div className="p-12 text-center text-xs text-slate-400 font-medium bg-[#fafafa]/50 border border-dashed border-gray-200 rounded-xl space-y-1.5">
                    <FileText className="w-8 h-8 text-gray-300 mx-auto" />
                    <p>暂无本群组历史总结记录。</p>
                    <p className="text-[10px] text-gray-400">在 Telegram 发送消息后，由 Bot 自动轮调或在群组详情手动触发即可生成成果。</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {groupSummaries.map((s) => {
                      const isSuccess = s.status === 'succeeded';
                      const isFailed = s.status === 'failed' || s.status === 'blocked';
                      return (
                        <div
                          key={s.id}
                          onClick={() => isSuccess && setSelectedSummary(s)}
                          className={`p-4 border rounded-xl flex items-center justify-between gap-4 transition-all ${
                            isSuccess
                              ? 'border-gray-200 hover:border-indigo-300 hover:bg-indigo-50/10 cursor-pointer shadow-2xs'
                              : 'border-gray-150 bg-gray-50/40 opacity-80'
                          }`}
                        >
                          <div className="space-y-1 min-w-0">
                            <div className="flex items-center flex-wrap gap-2">
                              <span className="text-xs font-bold text-gray-900 font-mono bg-gray-100 border border-gray-200/60 px-1.5 py-0.5 rounded leading-none">
                                #{s.sequence_range || '1001-1050'}
                              </span>
                              <span className="text-[10px] text-gray-405 font-medium">消息段</span>
                              <span className="text-gray-300 select-none">|</span>
                              <span className="text-[10px] text-indigo-650 font-bold uppercase tracking-wide">
                                {s.profile_name || '未绑定模板'}
                              </span>
                            </div>
                            <div className="text-[11px] text-gray-400 flex items-center gap-1.5 font-mono">
                              <Calendar className="w-3.5 h-3.5" />
                              <span>{s.finished_at ? new Date(s.finished_at).toLocaleString() : '处理中'}</span>
                            </div>
                          </div>

                          <div className="flex items-center gap-2.5 shrink-0">
                            {isSuccess ? (
                              <span className="px-2.5 py-1 text-[10px] font-bold text-emerald-600 bg-emerald-50 rounded-full border border-emerald-200/60 flex items-center gap-1 leading-none">
                                <Check className="w-3.5 h-3.5 stroke-[3]" />
                                <span>成功</span>
                              </span>
                            ) : isFailed ? (
                              <span
                                className="px-2.5 py-1 text-[10px] font-bold text-rose-500 bg-rose-50 rounded-full border border-rose-200/40 flex items-center gap-1 cursor-help leading-none"
                                title={s.error_message || '服务异常'}
                              >
                                <XCircle className="w-3.5 h-3.5" />
                                <span>失败</span>
                              </span>
                            ) : (
                              <span className="px-2.5 py-1 text-[10px] font-semibold text-blue-500 bg-blue-50 rounded-full border border-blue-200/40 flex items-center gap-1 animate-pulse leading-none">
                                <Clock className="w-3.5 h-3.5 animate-spin" />
                                <span>生成中</span>
                              </span>
                            )}
                            {isSuccess && (
                              <ChevronRight className="w-4 h-4 text-gray-400" />
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* Footer */}
              <div className="px-6 py-3 border-t border-gray-150 flex justify-end bg-[#fafafa] shrink-0">
                <button
                  onClick={() => setViewingGroup(null)}
                  className="px-4 py-1.5 bg-white border border-gray-200 hover:bg-slate-50 hover:border-gray-300 text-gray-700 rounded-lg text-xs font-semibold cursor-pointer transition-all"
                >
                  关闭
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>

      {/* 摘要详情查看二级弹窗 */}
      <AnimatePresence>
        {selectedSummary && (
          <div
            className="fixed inset-0 bg-black/45 backdrop-blur-xs flex items-center justify-center z-[60] p-4 animate-in fade-in duration-150"
            onClick={() => setSelectedSummary(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-2xl bg-white rounded-xl border border-gray-250 shadow-2xl overflow-hidden flex flex-col max-h-[85vh]"
            >
              {/* Header */}
              <div className="px-6 py-4 border-b border-gray-200 bg-[#fbfbfe] flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="p-2 bg-indigo-50/70 border border-indigo-100 text-indigo-600 rounded-lg shrink-0">
                    <FileText className="w-4.5 h-4.5 shrink-0" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 text-[15px]">
                      摘要归档查看
                    </h3>
                    <span className="text-[10px] text-gray-400 block font-mono mt-0.5">
                      任务批次 ID: {selectedSummary.id}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedSummary(null)}
                  className="p-1.5 px-2 bg-white text-xs border border-gray-200 hover:bg-slate-50 cursor-pointer hover:border-gray-300 text-gray-400 hover:text-gray-650 rounded-lg transition-all"
                >
                  <X className="w-4.5 h-4.5" />
                </button>
              </div>

              {/* Sub-meta details strip */}
              <div className="px-6 py-2 bg-slate-50/70 border-b border-[#e4e6ec] text-[10px] text-gray-500 font-mono grid grid-cols-2 sm:grid-cols-3 gap-2 shrink-0">
                <div>
                  <span className="text-gray-400 select-none">所属群组: </span>
                  <span className="text-gray-800 font-bold">{selectedSummary.group_title || `群组 ${selectedSummary.chat_id}`}</span>
                </div>
                <div>
                  <span className="text-gray-400 select-none">Profile 模板: </span>
                  <span className="text-gray-750 font-bold uppercase">{selectedSummary.profile_name || '未绑定模板'}</span>
                </div>
                <div className="col-span-2 sm:col-span-1">
                  <span className="text-gray-400 select-none">归档时间: </span>
                  <span className="text-gray-800 font-bold">
                    {selectedSummary.finished_at ? new Date(selectedSummary.finished_at).toLocaleString() : ''}
                  </span>
                </div>
              </div>

              {/* Body */}
              <div className="p-6 overflow-y-auto flex-1 bg-white select-text">
                <div className="bg-[#fafbfd] border border-gray-150 rounded-lg p-5 sm:p-7 shadow-2xs">
                  {renderSummaryMarkdown(selectedSummary.content)}
                </div>
              </div>

              {/* Footer */}
              <div className="px-6 py-3 border-t border-gray-150 flex justify-end gap-2.5 bg-[#fafafa] shrink-0">
                <button
                  onClick={() => {
                    if (selectedSummary.content) {
                      navigator.clipboard
                        .writeText(selectedSummary.content)
                        .then(() => {
                          showToast({
                            tone: 'success',
                            title: '已复制 Markdown 摘要'
                          });
                        })
                        .catch((err: any) => {
                          showToast({
                            tone: 'error',
                            title: '复制失败',
                            detail: err.message
                          });
                        });
                    }
                  }}
                  className="px-4 py-1.5 text-xs font-semibold text-gray-700 hover:text-gray-95 hover:bg-gray-50 border border-gray-200 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1"
                >
                  复制 Markdown 简盘
                </button>
                <button
                  onClick={() => setSelectedSummary(null)}
                  className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-gray-700 rounded-lg text-xs font-semibold cursor-pointer transition-all"
                >
                  返回上级
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Inline custom Markdown renderer to parse and render styled summary structures perfectly
function renderSummaryMarkdown(text: string | null | undefined) {
  if (!text) return <p className="text-gray-400 italic text-xs">无生成的生成报告内容。</p>;

  const lines = text.split('\n');

  return (
    <div className="space-y-4 font-sans text-xs sm:text-sm text-gray-800 leading-relaxed max-w-full overflow-hidden">
      {lines.map((line, idx) => {
        const trimmed = line.trim();

        // 1. Headers ###
        if (trimmed.startsWith('###')) {
          const hText = trimmed.replace('###', '').trim();
          return (
            <h3 key={idx} className="text-sm sm:text-base font-bold text-gray-900 pt-3 pb-1 border-b border-gray-100 mt-4 flex items-center gap-1.5 leading-none animate-in duration-300">
              <span className="w-1.5 h-3.5 bg-indigo-500 rounded-sm" />
              {hText}
            </h3>
          );
        }

        // 2. Sub-headers ####
        if (trimmed.startsWith('####')) {
          const hText = trimmed.replace('####', '').trim();
          return (
            <h4 key={idx} className="text-xs sm:text-sm font-bold text-gray-900 pt-2 pb-0.5 mt-3 leading-none uppercase tracking-wide">
              {hText}
            </h4>
          );
        }

        // 3. Bold lists or meta-blocks
        if (trimmed.startsWith('**') && trimmed.endsWith('**')) {
          const plainText = trimmed.replace(/\*\*/g, '').trim();
          return <div key={idx} className="font-bold text-gray-800 text-xs py-0.5">{plainText}</div>;
        }

        // 4. Todo list item with checkbox [ ] or [x]
        if (trimmed.startsWith('- [ ]') || trimmed.startsWith('- [x]')) {
          const isChecked = trimmed.startsWith('- [x]');
          const content = trimmed.substring(5).trim();

          const formattedContent = content.split(' ').map((word, wIdx) => {
            if (word.startsWith('@')) {
              return <span key={wIdx} className="text-indigo-650 font-semibold bg-indigo-50 px-1 py-0.5 rounded mr-1 font-mono text-[11px]">{word}</span>;
            }
            if (word.startsWith('【') && word.endsWith('】')) {
              return <span key={wIdx} className="text-gray-800 font-bold mr-1">{word}</span>;
            }
            return word + ' ';
          });

          return (
            <div key={idx} className="flex items-start gap-2.5 py-1.5 px-3 bg-[#fafbfd] hover:bg-slate-50 rounded-lg border border-slate-100 transition-colors">
              <div className={`w-4 h-4 rounded mt-0.5 shrink-0 flex items-center justify-center border transition-all ${
                isChecked
                  ? 'bg-emerald-500 border-emerald-500 text-white'
                  : 'bg-white border-slate-300 text-transparent'
              }`}>
                <Check className="w-3 h-3 stroke-[3]" />
              </div>
              <p className="text-xs text-gray-750 flex-1 leading-normal select-text">
                {formattedContent}
              </p>
            </div>
          );
        }

        // 5. Normal bullet items
        if (trimmed.startsWith('-') || trimmed.startsWith('*')) {
          const rawContent = trimmed.substring(1).trim();
          const parts = rawContent.split('**');
          let contentNode = null;
          if (parts.length >= 3) {
            contentNode = (
              <span>
                <strong className="text-gray-900 font-bold">{parts[1]}</strong>
                {parts.slice(2).join('**')}
              </span>
            );
          } else {
            contentNode = <span>{rawContent}</span>;
          }

          const subMerged = rawContent.split('`');
          if (subMerged.length >= 3) {
            contentNode = (
              <span>
                {subMerged[0]}
                <code className="bg-slate-100 border border-slate-200 text-gray-800 font-mono text-[10px] px-1.5 py-0.5 rounded font-semibold mx-1">{subMerged[1]}</code>
                {subMerged[2]}
              </span>
            );
          }

          return (
            <div key={idx} className="flex gap-2 pl-2">
              <span className="text-gray-400 select-none mt-1.5 flex h-1.5 w-1.5 rounded-full bg-indigo-400 shrink-0" />
              <p className="text-xs text-gray-650 leading-normal flex-1 select-text">{contentNode}</p>
            </div>
          );
        }

        // 6. Horizontal separator ---
        if (trimmed === '---') {
          return <hr key={idx} className="border-t border-[#f0f1f4] my-4 block" />;
        }

        // 7. Non-empty string
        if (trimmed.length > 0) {
          const processedText = trimmed.split('**').map((tok, tIdx) => {
            if (tIdx % 2 === 1) {
              return <strong key={tIdx} className="text-gray-900 font-semibold">{tok}</strong>;
            }
            const codeSplits = tok.split('`');
            return codeSplits.map((subTok, scIdx) => {
              if (scIdx % 2 === 1) {
                return <code key={scIdx} className="bg-gray-50 text-gray-850 border border-gray-150 font-mono text-[10px] px-1 py-0.5 rounded mx-0.5 font-bold">{subTok}</code>;
              }
              return subTok;
            });
          });

          return <p key={idx} className="text-xs text-slate-705 select-text leading-relaxed">{processedText}</p>;
        }

        return null;
      })}
    </div>
  );
}
