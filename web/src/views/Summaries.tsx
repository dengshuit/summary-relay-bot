import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { HistoricalSummary } from '../api/types';
import CustomSelect from '../components/CustomSelect';
import {
  FileText,
  Search,
  Filter,
  Clock,
  Sparkles,
  RefreshCw,
  CheckCircle,
  XCircle,
  AlertCircle,
  ExternalLink,
  Bot,
  ChevronRight,
  TrendingUp,
  X,
  Check,
  Calendar
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useToast } from '../components/Toast';

export default function Summaries() {
  const showToast = useToast();
  const location = useLocation();
  const [summaries, setSummaries] = useState<HistoricalSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorText, setErrorText] = useState<string | null>(null);

  // Search/Filter States
  const [searchQuery, setSearchQuery] = useState(() => {
    const params = new URLSearchParams(window.location.search);
    return params.get('search') || '';
  });
  const [statusFilter, setStatusFilter] = useState('');

  // Sync from query params if state changes
  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const q = params.get('search');
    if (q !== null) {
      setSearchQuery(q);
    }
  }, [location.search]);

  // Selected summary for rendering inside overlay Modal
  const [selectedSummary, setSelectedSummary] = useState<HistoricalSummary | null>(null);

  const fetchSummaries = async () => {
    setLoading(true);
    setErrorText(null);
    try {
      const res = await api.getSummaries();
      setSummaries(res.items);
    } catch (err: any) {
      setErrorText(err.message || '搭载历史总结存档异常');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchSummaries();
  }, []);

  // Filter local logic
  const filteredSummaries = summaries.filter(s => {
    const normalizedQuery = searchQuery.toLowerCase();
    const groupTitle = (s.group_title || '').toLowerCase();
    const groupUsername = (s.group_username || '').toLowerCase();
    const chatId = String(s.chat_id);
    const titleMatch = groupTitle.includes(normalizedQuery) ||
                       groupUsername.includes(normalizedQuery) ||
                       chatId.includes(searchQuery);
    const statusMatch = statusFilter === '' ? true : s.status === statusFilter;
    return titleMatch && statusMatch;
  });

  // Derived telemetry metrics
  const totalCount = summaries.length;
  const succeededCount = summaries.filter(s => s.status === 'succeeded').length;
  const failedCount = summaries.filter(s => s.status === 'failed' || s.status === 'blocked').length;
  const pendingCount = summaries.filter(s => s.status === 'pending' || s.status === 'running').length;

  // Custom Inline Markdown-to-TSX element renderer
  // Ensures robust styling without additional MD parser rendering bugs
  const renderSummaryMarkdown = (text: string | null | undefined) => {
    if (!text) return <p className="text-gray-400 italic text-xs">无生成的生成报告内容。</p>;

    const lines = text.split('\n');
    let insideTodoBlock = false;

    return (
      <div className="space-y-4 font-sans text-xs sm:text-sm text-gray-800 leading-relaxed max-w-full overflow-hidden">
        {lines.map((line, idx) => {
          const trimmed = line.trim();

          // 1. Headers ###
          if (trimmed.startsWith('###')) {
            const hText = trimmed.replace('###', '').trim();
            return (
              <h3 key={idx} className="text-sm sm:text-base font-bold text-gray-900 pt-3 pb-1 border-b border-gray-100 mt-4 flex items-center gap-1.5 leading-none">
                <span className="w-1.5 h-3.5 bg-gray-400 rounded-sm" />
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

            // Format highlights like @names
            const formattedContent = content.split(' ').map((word, wIdx) => {
              if (word.startsWith('@')) {
                return <span key={wIdx} className="text-gray-900 font-semibold bg-gray-100 px-1 py-0.5 rounded mr-1 font-mono text-[11px]">{word}</span>;
              }
              if (word.startsWith('【') && word.endsWith('】')) {
                return <span key={wIdx} className="text-gray-800 font-bold mr-1">{word}</span>;
              }
              return word + ' ';
            });

            return (
              <div key={idx} className="flex items-start gap-2.5 py-1.5 px-3 bg-slate-50/50 hover:bg-slate-50 rounded-lg border border-slate-100 transition-colors">
                <div className={`w-4 h-4 rounded mt-0.5 shrink-0 flex items-center justify-center border transition-all ${
                  isChecked
                    ? 'bg-emerald-500 border-emerald-500 text-white'
                    : 'bg-white border-slate-300 text-transparent'
                }`}>
                  <Check className="w-3 h-3 stroke-[3]" />
                </div>
                <p className="text-xs text-gray-700 flex-1 leading-normal select-text">
                  {formattedContent}
                </p>
              </div>
            );
          }

          // 5. Normal bullet items
          if (trimmed.startsWith('-') || trimmed.startsWith('*')) {
            const rawContent = trimmed.substring(1).trim();
            // Highlighting inline bold e.g. **名称**: 内容
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

            // Highlighting inline code block in list
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
                <span className="text-gray-400 select-none mt-1.5 flex h-1.5 w-1.5 rounded-full bg-gray-400 shrink-0" />
                <p className="text-xs text-gray-600 leading-normal flex-1 select-text">{contentNode}</p>
              </div>
            );
          }

          // 6. Horizontal separator ---
          if (trimmed === '---') {
            return <hr key={idx} className="border-t border-[#f0f1f4] my-4 block" />;
          }

          // 7. Non-empty string
          if (trimmed.length > 0) {
            // Check for standard meta details bold tags
            // Process bold words in lines
            const processedText = trimmed.split('**').map((tok, tIdx) => {
              if (tIdx % 2 === 1) {
                return <strong key={tIdx} className="text-gray-900 font-semibold">{tok}</strong>;
              }
              // Code block token highlights
              const codeSplits = tok.split('`');
              return codeSplits.map((subTok, scIdx) => {
                if (scIdx % 2 === 1) {
                  return <code key={scIdx} className="bg-gray-50 text-gray-800 border border-gray-150 font-mono text-[10px] px-1 py-0.5 rounded mx-0.5 font-bold">{subTok}</code>;
                }
                return subTok;
              });
            });

            return <p key={idx} className="text-xs text-slate-700 select-text leading-relaxed">{processedText}</p>;
          }

          return null;
        })}
      </div>
    );
  };

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">

      {/* Title Header */}
      <div className="flex justify-between items-center animate-in fade-in slide-in-from-top-4 duration-200">
        <div>
          <h2 className="text-[24px] font-semibold text-gray-900 leading-none">历史摘要成果</h2>
        </div>
      </div>

      {/* Dynamic Telemetry Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 animate-in fade-in duration-300">
        {/* Total stats */}
        <div className="bg-white border border-gray-200 p-4 rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider block">任务总量</span>
            <span className="text-xl font-extrabold text-gray-950 font-mono tracking-tight">{totalCount}</span>
          </div>
          <div className="p-2 bg-gray-50 border border-gray-150 rounded-lg text-gray-400 shrink-0">
            <FileText className="w-5 h-5" />
          </div>
        </div>

        {/* Succeeded stats */}
        <div className="bg-white border border-gray-200 p-4 rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider block">成功归档</span>
            <span className="text-xl font-extrabold text-gray-900 font-mono tracking-tight">{succeededCount}</span>
          </div>
          <div className="p-2 bg-gray-50 border border-gray-150 rounded-lg text-gray-400 shrink-0">
            <CheckCircle className="w-5 h-5" />
          </div>
        </div>

        {/* Failed stats */}
        <div className="bg-white border border-gray-200 p-4 rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider block">运行失败</span>
            <span className="text-xl font-extrabold text-gray-900 font-mono tracking-tight">{failedCount}</span>
          </div>
          <div className="p-2 bg-gray-50 border border-gray-150 rounded-lg text-gray-400 shrink-0">
            <XCircle className="w-5 h-5" />
          </div>
        </div>

        {/* Active stats */}
        <div className="bg-white border border-gray-200 p-4 rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex items-center justify-between">
          <div className="space-y-1">
            <span className="text-[10px] text-gray-400 font-semibold uppercase tracking-wider block">排队/处理中</span>
            <span className={`text-xl font-extrabold font-mono tracking-tight ${pendingCount > 0 ? 'text-gray-900 animate-pulse' : 'text-gray-405'}`}>
              {pendingCount}
            </span>
          </div>
          <div className="p-2 bg-gray-50 border border-gray-150 rounded-lg text-gray-400 shrink-0">
            <Clock className="w-5 h-5" />
          </div>
        </div>
      </div>

      {/* Filter and Search controls */}
      <div className="bg-white border border-gray-200 rounded-lg p-4 shadow-[0_1px_2px_rgba(0,0,0,0.03)] flex flex-col sm:flex-row gap-3 items-center justify-between">
        <div className="relative w-full sm:w-[320px]">
          <span className="absolute inset-y-0 left-0 pl-3 flex items-center text-gray-400 pointer-events-none">
            <Search className="w-4 h-4 shrink-0" />
          </span>
          <input
            type="text"
            placeholder="搜索群组名称 / 频道号 / ID..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-9 pr-4 py-2 bg-white border border-gray-200 rounded-lg text-[15px] text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-indigo-500 h-10 leading-normal transition-colors"
          />
        </div>

        <div className="flex gap-2 w-full sm:w-56 shrink-0 justify-end z-20">
          <CustomSelect
            options={[
              { value: "", label: "全部状态" },
              { value: "succeeded", label: "生成成功" },
              { value: "failed", label: "摘要失败" },
              { value: "running", label: "正在生成" }
            ]}
            value={statusFilter}
            onChange={(val) => setStatusFilter(val)}
            placeholder="筛选生成状态"
          />
        </div>
      </div>

      {/* List / Table Section */}
      <div className="bg-white border border-gray-200 rounded-lg overflow-hidden shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
        {loading && summaries.length === 0 ? (
          <div className="p-12 flex flex-col items-center justify-center gap-3">
            <RefreshCw className="w-7 h-7 text-gray-400 animate-spin" />
            <span className="text-xs text-gray-400 font-medium">正在加载摘要...</span>
          </div>
        ) : errorText ? (
          <div className="p-8 text-center text-xs text-rose-500 leading-relaxed font-semibold">
            {errorText}
          </div>
        ) : filteredSummaries.length === 0 ? (
          <div className="p-12 text-center select-none text-xs text-slate-400 font-medium space-y-1.5 bg-[#fafafa]/50">
            <Sparkles className="w-8 h-8 text-gray-300 mx-auto" />
            <p>暂无符合条件的摘要。</p>
            <p className="text-[10px] text-gray-400">有新的摘要后会显示在这里。</p>
          </div>
        ) : (
          <div className="overflow-x-auto min-w-full">
            <table className="min-w-full divide-y divide-gray-200 text-left">
              <thead className="bg-[#fafbfd] text-[10px] text-gray-400 uppercase font-bold tracking-wider">
                <tr>
                  <th className="px-5 py-3">聊天群组信息</th>
                  <th className="px-5 py-3">摘要配置 Profile</th>
                  <th className="px-5 py-3">运行周期</th>
                  <th className="px-5 py-3">归档时间</th>
                  <th className="px-5 py-3 text-center">状态</th>
                  <th className="px-5 py-3 text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 text-[14px] font-medium text-gray-700">
                {filteredSummaries.map((s, idx) => {
                  const hasError = s.status === 'failed' || s.status === 'blocked';
                  const isRunning = s.status === 'running' || s.status === 'pending';

                  return (
                    <tr key={s.id} className="hover:bg-[#fafbfd]/80 transition-colors">
                      {/* Group cell */}
                      <td className="px-5 py-4">
                        <div className="space-y-0.5">
                          <span className="text-gray-900 font-bold block truncate max-w-[170px]" title={s.group_title || `群组 ${s.chat_id}`}>
                            {s.group_title || `群组 ${s.chat_id}`}
                          </span>
                          <span className="text-[10px] text-gray-400 font-mono block">
                            {s.group_username ? `@${s.group_username}` : `ID: ${s.chat_id}`}
                          </span>
                        </div>
                      </td>

                      {/* Profile cell */}
                      <td className="px-5 py-4">
                        <div className="space-y-0.5">
                          <span className="text-gray-800 font-semibold block uppercase text-[10px]">
                            {s.profile_name || '未绑定模板'}
                          </span>
                          <span className="text-[10px] text-gray-500 block bg-gray-100 px-1.5 py-0.5 rounded w-max font-mono border border-gray-200/40">
                            {s.provider || '未绑定 Provider'} / {s.model || '未记录模型'}
                          </span>
                        </div>
                      </td>

                      {/* Range index */}
                      <td className="px-5 py-4">
                        <div className="flex items-center gap-1.5 text-gray-500 font-mono">
                          <span className="text-[10px] text-gray-500 font-semibold bg-gray-100 border border-gray-200/40 px-1.5 py-0.5 rounded shrink-0">
                            #{s.sequence_range || '1001-1050'}
                          </span>
                          <span className="text-[10px] text-slate-400">消息段</span>
                        </div>
                      </td>

                      {/* Archived Date */}
                      <td className="px-5 py-4 font-mono text-[10px] text-gray-500">
                        {s.finished_at ? (
                          <div className="space-y-0.5">
                            <span className="block text-gray-700 font-medium">
                              {new Date(s.finished_at).toLocaleDateString()}
                            </span>
                            <span className="block text-gray-400 text-[9px]">
                              {new Date(s.finished_at).toLocaleTimeString()}
                            </span>
                          </div>
                        ) : (
                          <span className="italic text-gray-400">运行队列中...</span>
                        )}
                      </td>

                      {/* Status Badging */}
                      <td className="px-5 py-4 text-center">
                        {s.status === 'succeeded' ? (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-200/60 rounded-full">
                            <Check className="w-3 h-3 stroke-[3]" />
                            <span>归档成功</span>
                          </span>
                        ) : hasError ? (
                          <span
                            className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-bold text-rose-500 bg-rose-50 border border-rose-100 rounded-full cursor-help"
                            title={s.error_message || '服务推理被拒绝'}
                          >
                            <AlertCircle className="w-3 h-3" />
                            <span>失败</span>
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-semibold text-gray-650 bg-gray-50 border border-gray-200 rounded-full animate-pulse">
                            <RefreshCw className="w-3 h-3 animate-spin" />
                            <span>处理中</span>
                          </span>
                        )}
                      </td>

                      {/* Actions */}
                      <td className="px-5 py-4 text-right">
                        {s.status === 'succeeded' ? (
                          <button
                            onClick={() => setSelectedSummary(s)}
                            className="px-3 py-1.5 text-xs text-gray-700 hover:text-gray-900 hover:bg-gray-50 border border-gray-200 rounded-lg hover:shadow-2xs transition-all font-semibold inline-flex items-center gap-1 cursor-pointer"
                          >
                            <span>查看成果</span>
                            <ChevronRight className="w-3.5 h-3.5 shrink-0" />
                          </button>
                        ) : hasError ? (
                          <button
                            disabled
                            className="px-3 py-1.5 text-xs text-gray-400 border border-gray-100 bg-[#fafafa] rounded-lg cursor-not-allowed select-none"
                            title={s.error_message || '不可看'}
                          >
                            不可看
                          </button>
                        ) : (
                          <span className="text-[10px] text-gray-400 italic font-medium px-3 block">计算生成中</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Styled Summary Preview Overlay Dialog (Modal) */}
      <AnimatePresence>
        {selectedSummary && (
          <div
            className="fixed inset-0 bg-black/45 backdrop-blur-xs flex items-center justify-center z-50 p-4"
            onClick={() => setSelectedSummary(null)}
          >
            <motion.div
              initial={{ scale: 0.95, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.95, opacity: 0 }}
              transition={{ duration: 0.15 }}
              onClick={(e) => e.stopPropagation()}
              className="w-full max-w-2xl bg-white rounded-lg border border-gray-250 shadow-[0_4px_12px_rgba(0,0,0,0.05)] overflow-hidden flex flex-col max-h-[85vh]"
            >
              {/* Modal Header */}
              <div className="px-6 py-4 border-b border-gray-200 bg-[#fbfbfe] flex justify-between items-center shrink-0">
                <div className="flex items-center gap-2">
                  <div className="p-1.5 bg-gray-50 border border-gray-150 text-gray-500 rounded-lg">
                    <FileText className="w-4 h-4 shrink-0" />
                  </div>
                  <div>
                    <h3 className="font-bold text-gray-900 text-sm">
                      摘要归档查看
                    </h3>
                    <span className="text-[10px] text-gray-400 block font-mono">
                      任务批次号: {selectedSummary.id}
                    </span>
                  </div>
                </div>
                <button
                  onClick={() => setSelectedSummary(null)}
                  className="p-1 px-2 text-xs border border-gray-200 hover:bg-slate-50 cursor-pointer hover:border-gray-300 text-gray-400 hover:text-gray-600 rounded-lg transition-all"
                >
                  <X className="w-4 h-4" />
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
                  <span className="text-gray-800 font-bold">{selectedSummary.finished_at ? new Date(selectedSummary.finished_at).toLocaleString() : ''}</span>
                </div>
              </div>

              {/* Modal Markdown Body Panel */}
              <div className="p-6 overflow-y-auto flex-1 bg-white select-text">
                <div className="bg-[#fafbfd] border border-gray-150 rounded-lg p-5 sm:p-7 shadow-none">
                  {renderSummaryMarkdown(selectedSummary.content)}
                </div>
              </div>

              {/* Modal Footer actions */}
              <div className="px-6 py-3 border-t border-gray-150 flex justify-end gap-2 bg-[#fafafa] shrink-0">
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
                  className="px-4 py-1.5 text-xs font-semibold text-gray-700 hover:text-gray-900 hover:bg-gray-50 border border-gray-200 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1"
                >
                  复制 Markdown 简盘
                </button>
                <button
                  onClick={() => setSelectedSummary(null)}
                  className="px-4 py-1.5 bg-slate-100 hover:bg-slate-200 text-gray-700 rounded-lg text-xs font-semibold cursor-pointer transition-all"
                >
                  关闭页面
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
}
