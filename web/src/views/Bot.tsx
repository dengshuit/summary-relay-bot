import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { BotInstance, DashboardData } from '../api/types';
import {
  RefreshCw,
  Check,
  X,
  AlertCircle,
  Zap,
  HelpCircle
} from 'lucide-react';

type SaveNotice = {
  kind: 'success' | 'error' | 'info';
  title: string;
  detail?: string;
};

export default function BotConfig() {
  const [bots, setBots] = useState<BotInstance[]>([]);
  const [selectedBotId, setSelectedBotId] = useState<number | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [runtimeStatus, setRuntimeStatus] = useState<DashboardData['telegram_startup'] | null>(null);
  const [saveNotice, setSaveNotice] = useState<SaveNotice | null>(null);

  // Edit fields
  const [name, setName] = useState('');
  const [ownerId, setOwnerId] = useState('');
  const [enabled, setEnabled] = useState(false);
  const [botToken, setBotToken] = useState('');
  const [saving, setSaving] = useState(false);

  // Validation modal state
  const [validating, setValidating] = useState(false);
  const [validationResult, setValidationResult] = useState<string | null>(null);
  const [validationSucceeded, setValidationSucceeded] = useState<boolean | null>(null);
  const [tempToken, setTempToken] = useState('');
  const [showValDialog, setShowValDialog] = useState(false);

  const fetchBots = async (selectId?: number | string) => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [res, dashboard] = await Promise.all([
        api.getBots(),
        api.getDashboard().catch(() => null),
      ]);
      setBots(res.items);
      setRuntimeStatus(dashboard?.telegram_startup ?? null);
      const activeId = selectId ? Number(selectId) : (res.active ?? res.items[0]?.id ?? null);
      setSelectedBotId(activeId);
      loadBotFields(activeId, res.items);
    } catch (err: any) {
      setErrorMsg(err.message || '获取 Bot 实例清单失败');
    } finally {
      setLoading(false);
    }
  };

  const resetBotFields = () => {
    setName('');
    setOwnerId('');
    setEnabled(false);
    setBotToken('');
  };

  const loadBotFields = (id: number | null, list: BotInstance[]) => {
    const current = list.find(b => b.id === id);
    if (current) {
      setName(current.name);
      setOwnerId(''); // always blank for update (replacement-only)
      setEnabled(current.enabled);
      setBotToken(''); // replacement-only
    } else {
      resetBotFields();
    }
  };

  useEffect(() => {
    fetchBots();
  }, []);

  const handleSelectBot = (id: string) => {
    const numericId = Number(id);
    setSelectedBotId(numericId);
    loadBotFields(numericId, bots);
  };

  const selectedBot = bots.find(b => b.id === selectedBotId);
  const isCreateMode = bots.length === 0 || selectedBotId === null || selectedBot === undefined;
  const isUnconfigured = bots.length === 0;
  const runtimeRunning = runtimeStatus?.status === 'running';
  const runtimeLabel = runtimeStatus
    ? runtimeRunning
      ? '运行中'
      : runtimeStatus.status === 'failed'
        ? '启动失败'
        : runtimeStatus.status === 'no_enabled_bot'
          ? '未启用'
          : runtimeStatus.status
    : '未知';
  const saveNoticeStyle = saveNotice?.kind === 'success'
    ? {
        container: 'bg-emerald-50 border-emerald-200',
        icon: 'text-emerald-600',
        title: 'text-emerald-900',
        detail: 'text-emerald-700',
      }
    : saveNotice?.kind === 'error'
      ? {
          container: 'bg-rose-50 border-rose-200',
          icon: 'text-rose-600',
          title: 'text-rose-900',
          detail: 'text-rose-700',
        }
      : {
          container: 'bg-slate-50 border-slate-200',
          icon: 'text-slate-500',
          title: 'text-slate-900',
          detail: 'text-slate-600',
        };

  const validateSavedBot = async (botId: number | string): Promise<SaveNotice> => {
    const result = await api.validateBot({
      id: botId,
      bot_token: null,
    });

    if (result.success) {
      return {
        kind: 'success',
        title: '保存并校验成功',
      };
    }

    return {
      kind: 'error',
      title: '保存成功，校验失败',
      detail: result.detail || result.error_message || 'Token 校验未通过。',
    };
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaveNotice(null);

    if (isCreateMode) {
      if (!name.trim() || !ownerId.trim() || !botToken.trim()) {
        setSaveNotice({
          kind: 'error',
          title: '保存失败',
          detail: '请填入 Bot 别名、所有者 Telegram ID 和 Bot Token 后再保存。',
        });
        return;
      }

      setSaving(true);
      try {
        const newBot = await api.createBot({
          name: name.trim(),
          owner_id: ownerId.trim(),
          enabled,
          bot_token: botToken.trim()
        });
        let nextNotice: SaveNotice;
        try {
          nextNotice = await validateSavedBot(newBot.id);
        } catch (validationErr: any) {
          nextNotice = {
            kind: 'error',
            title: '保存成功，校验异常',
            detail: validationErr.message || 'Token 校验请求失败。',
          };
        }

        setBotToken('');
        setOwnerId('');
        await fetchBots(newBot.id);
        setSaveNotice(nextNotice);
      } catch (err: any) {
        setSaveNotice({
          kind: 'error',
          title: '保存失败',
          detail: err.message || '创建 Bot 配置失败。',
        });
      } finally {
        setSaving(false);
      }
      return;
    }

    if (!selectedBot) return;

    const trimmedName = name.trim();
    if (!trimmedName) {
      setSaveNotice({
        kind: 'error',
        title: '保存失败',
        detail: 'Bot 别名不能为空。',
      });
      return;
    }

    const updatePayload: any = { id: selectedBotId };
    if (trimmedName !== selectedBot.name) updatePayload.name = trimmedName;
    if (ownerId.trim() !== '') updatePayload.owner_id = ownerId.trim();
    if (enabled !== selectedBot.enabled) updatePayload.enabled = enabled;
    if (botToken.trim() !== '') updatePayload.bot_token = botToken.trim();

    if (Object.keys(updatePayload).length === 1) {
      setSaveNotice({
        kind: 'info',
        title: '无可提交变更',
      });
      return;
    }

    // If enabling this bot, and there's another enabled bot
    const otherEnabled = bots.some(b => b.enabled && b.id !== selectedBotId);
    if (updatePayload.enabled === true && otherEnabled) {
      const confirmSwitch = window.confirm(
        '当前系统只允许同时启用一个 Bot 实例。启用此 Bot 会自动禁用其他所有实例，并触发 Bot polling 运行时重新加载。是否确认切换？'
      );
      if (!confirmSwitch) return;
    }

    setSaving(true);
    try {
      await api.updateBot(updatePayload);
      let nextNotice: SaveNotice;
      try {
        nextNotice = await validateSavedBot(selectedBotId);
      } catch (validationErr: any) {
        nextNotice = {
          kind: 'error',
          title: '保存成功，校验异常',
          detail: validationErr.message || 'Token 校验请求失败。',
        };
      }

      setBotToken('');
      setOwnerId('');
      await fetchBots(selectedBotId);
      setSaveNotice(nextNotice);
    } catch (err: any) {
      setSaveNotice({
        kind: 'error',
        title: '保存失败',
        detail: err.message || '更新 Bot 配置失败。',
      });
    } finally {
      setSaving(false);
    }
  };

  const handleValidateConnection = async () => {
    setValidating(true);
    setValidationResult(null);
    setValidationSucceeded(null);
    try {
      if (selectedBotId === null) return;
      const res = await api.validateBot({
        id: selectedBotId,
        bot_token: tempToken.trim() ? tempToken : null,
      });
      setValidationSucceeded(res.success);
      setValidationResult(res.detail || '已成功建立 Bot 双向通讯。');
      await fetchBots(selectedBotId);
    } catch (err: any) {
      setValidationSucceeded(false);
      setValidationResult('校验发生不可恢复的错误: ' + err.message);
    } finally {
      setValidating(false);
    }
  };

  if (loading && bots.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-2">
        <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin" />
        <p className="text-sm text-gray-500">正在获取 Telegram Poller 数据库信息...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* Needs Restart Warning Bar */}
      {selectedBot?.needs_restart && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 animate-pulse">
          <div className="flex items-start gap-3">
            <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <h4 className="text-xs font-semibold text-amber-900 uppercase tracking-widest">Bot 变更处于未加载态</h4>
              <p className="text-xs text-amber-700 mt-0.5">部分已修改属性尚未被 Telegram polling 运行时加载。可在工作台重新加载 Bot 运行时。</p>
            </div>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="px-3 py-1.5 bg-amber-500 hover:bg-amber-600 text-white rounded-lg text-xs font-semibold block shrink-0"
          >
            刷新工作台状态
          </button>
        </div>
      )}

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-[24px] font-semibold text-gray-900 leading-none">Bot 配置</h2>
        </div>
      </div>

      {errorMsg && (
        <div className="bg-rose-50 border border-rose-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-rose-600 mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-rose-900 uppercase tracking-widest">Bot 配置读取失败</h4>
            <p className="text-xs text-rose-700 mt-0.5">{errorMsg}</p>
          </div>
        </div>
      )}

      {isUnconfigured && !errorMsg && (
        <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 flex items-start gap-3">
          <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
          <div>
            <h4 className="text-xs font-semibold text-amber-900 uppercase tracking-widest">尚未配置 Bot</h4>
          </div>
        </div>
      )}

      {saveNotice && (
        <div className={`${saveNoticeStyle.container} border rounded-xl p-4 flex items-start gap-3`}>
          {saveNotice.kind === 'success' ? (
            <Check className={`w-5 h-5 ${saveNoticeStyle.icon} mt-0.5 shrink-0`} />
          ) : (
            <AlertCircle className={`w-5 h-5 ${saveNoticeStyle.icon} mt-0.5 shrink-0`} />
          )}
          <div>
            <h4 className={`text-xs font-semibold ${saveNoticeStyle.title} uppercase tracking-widest`}>{saveNotice.title}</h4>
            {saveNotice.detail && (
              <p className={`text-xs ${saveNoticeStyle.detail} mt-0.5`}>{saveNotice.detail}</p>
            )}
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Main Info Fields Form */}
          <div className="lg:col-span-8 bg-white border border-gray-200 rounded-lg shadow-[0_1px_2px_rgba(0,0,0,0.03)] overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200 bg-[#fbfbfe]">
              <span className="text-[10px] font-mono text-indigo-600 uppercase tracking-wider block">Configuration editor</span>
              <h3 className="text-[16px] font-semibold text-gray-900 mt-1">{isCreateMode ? '新增 Bot 配置' : '基本信息设置'}</h3>
            </div>

            <form onSubmit={handleSave} className="p-6 space-y-6">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Bot Name field */}
                <div className="space-y-2">
                  <label className="text-[15px] font-semibold text-gray-700 block">Bot 别名</label>
                  <input
                    type="text"
                    required
                    value={name}
                    onChange={(e) => {
                      setName(e.target.value);
                      setSaveNotice(null);
                    }}
                    placeholder="例如: 生产环境摘要Bot"
                    className="w-full px-3.5 py-2.5 rounded-lg border border-gray-200 text-[15px] text-gray-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 h-10 leading-normal"
                  />
                </div>

                {/* Owner ID (Redacted update style) */}
                <div className="space-y-2">
                  <label className="text-[15px] font-semibold text-gray-700 block">
                    管理专属 Operator 所有者 Telegram ID
                  </label>
                  <input
                    type="text"
                    required={isCreateMode}
                    value={ownerId}
                    onChange={(e) => {
                      setOwnerId(e.target.value);
                      setSaveNotice(null);
                    }}
                    placeholder={selectedBot?.owner_id_redacted ? `已脱敏: ${selectedBot.owner_id_redacted} (输入不为空进行覆盖)` : '输入数字形式 Telegram User ID'}
                    className="w-full px-3.5 py-2.5 rounded-lg border border-gray-200 text-[15px] text-gray-800 placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 font-mono h-10 leading-normal"
                  />
                </div>
              </div>

              {/* Bot Token Key Secret replacement input */}
              <div className="space-y-2">
                <label className="text-[15px] font-semibold text-gray-700 block mt-2">
                  {isCreateMode ? 'Bot API Token 密钥' : 'Bot API Token 密钥更换'}
                </label>
                <div className="relative">
                  <input
                    type="password"
                    required={isCreateMode}
                    value={botToken}
                    onChange={(e) => {
                      setBotToken(e.target.value);
                      setSaveNotice(null);
                    }}
                    placeholder={selectedBot?.secret.configured ? '密钥已配置。输入新 Bot Token 密码进行覆盖更换 (留空代表不作任何修改)' : '请填入格式为 (数字:字母) 的 Telegram Bot Token'}
                    className="w-full px-3.5 py-2.5 rounded-lg border border-gray-200 text-[15px] text-gray-800 placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 font-mono h-10 leading-normal"
                  />
                </div>
                {selectedBot?.secret.configured && (
                  <div className="flex items-center justify-between text-[10px] text-[#5f6672]">
                    <span className="flex items-center gap-1 font-mono text-green-600 bg-green-50 px-1 py-0.5 rounded-sm">
                      <Check className="w-3.5 h-3.5" /> 已在数据库安全存储。
                    </span>
                    <span>最后更换时间: {selectedBot.secret.updated_at ? new Date(selectedBot.secret.updated_at).toLocaleString() : '未知'}</span>
                  </div>
                )}
              </div>
              <div className="pt-4 border-t border-gray-100 flex items-center justify-between">
                <div className="space-y-0.5">
                  <span className="text-[15px] font-semibold text-gray-850 block">启用当前 Bot 在线轮询服务</span>
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enabled}
                    onChange={(e) => {
                      setEnabled(e.target.checked);
                      setSaveNotice(null);
                    }}
                    className="sr-only peer"
                  />
                  <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                </label>
              </div>

              {/* Actions Footer row */}
              <div className="pt-4 border-t border-gray-100 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => {
                    setSaveNotice(null);
                    isCreateMode ? resetBotFields() : loadBotFields(selectedBotId, bots);
                  }}
                  className="px-4 py-2 border border-gray-250 text-gray-500 hover:bg-gray-50 rounded-lg text-xs font-semibold cursor-pointer h-10 flex items-center justify-center"
                >
                  重置
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center justify-center gap-2 cursor-pointer shadow-sm disabled:opacity-50 h-10"
                >
                  {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>{isCreateMode ? '保存 Bot 配置' : '保存并应用配置'}</span>
                </button>
              </div>
            </form>
          </div>

          {/* Sidebar Status Info Card & Validate Tool */}
          <div className="lg:col-span-4 space-y-6">
            {/* Status card */}
            <div className="bg-white border border-gray-100 rounded-xl shadow-[0_4px_20px_rgba(0,0,0,0.02)] overflow-hidden transition-all duration-300 hover:shadow-[0_8px_30px_rgba(0,0,0,0.04)]">
              <div className="px-5 py-4 border-b border-gray-100/80 bg-slate-50/50">
                <h3 className="text-[14px] font-bold text-gray-800">Bot 状态及属性</h3>
              </div>
              <div className="p-5 space-y-4 text-[14px]">
                {/* Validator status line */}
                <div className="flex items-center justify-between">
                  <span className="text-gray-500 font-medium">Token 校验状态</span>
                  <span className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                    selectedBot?.status === 'valid'
                      ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                      : 'bg-amber-50 text-amber-700 border border-amber-100'
                  }`}>
                    {isCreateMode ? '尚未配置' : selectedBot?.status === 'valid' ? '校验通过' : '待校验'}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-gray-500 font-medium">上次校验时间</span>
                  <span className="font-mono text-gray-700 text-[13px] text-right font-medium">
                    {selectedBot?.last_validated_at ? new Date(selectedBot.last_validated_at).toLocaleTimeString() : isCreateMode ? '无配置' : '尚未校验'}
                  </span>
                </div>

                <div className="flex items-center justify-between">
                  <span className="text-gray-500 font-medium">Polling 运行时</span>
                  <span
                    className={`px-2 py-0.5 rounded text-[11px] font-bold ${
                      runtimeRunning
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-100'
                        : runtimeStatus?.status === 'failed'
                          ? 'bg-rose-50 text-rose-700 border border-rose-100'
                          : 'bg-slate-50 text-slate-600 border border-slate-200'
                    }`}
                    title={runtimeStatus?.detail || undefined}
                  >
                    {runtimeLabel}
                  </span>
                </div>

                <div className="border-t border-gray-100/80 my-2"></div>

                <div className="space-y-2">
                  <span className="text-[11px] text-gray-400 tracking-widest block font-bold uppercase">远程 API 网关注册信息：</span>
                  <div className="grid grid-cols-2 gap-2 mt-1 bg-gray-50/50 p-3 rounded-lg border border-gray-100 font-mono text-[12px] text-gray-600">
                    <div>
                      <span className="text-gray-400 block uppercase text-[9px] font-sans font-bold">Bot ID</span>
                      <strong className="text-gray-800 block mt-0.5 truncate font-bold">{selectedBot?.telegram_bot_id || '未知'}</strong>
                    </div>
                    <div>
                      <span className="text-gray-400 block uppercase text-[9px] font-sans font-bold">Username</span>
                      <strong className="text-gray-800 block mt-0.5 truncate font-bold">{selectedBot?.telegram_username ? `@${selectedBot.telegram_username}` : '待校验'}</strong>
                    </div>
                  </div>
                </div>

                <button
                  type="button"
                  disabled={isCreateMode}
                  title={isCreateMode ? '保存 Bot 配置后才能校验连接' : undefined}
                  onClick={() => {
                    if (isCreateMode) return;
                    setTempToken('');
                    setValidationResult(null);
                    setValidationSucceeded(null);
                    setShowValDialog(true);
                  }}
                  className="w-full h-10 border border-indigo-200 hover:border-indigo-300 text-indigo-600 bg-indigo-50/30 hover:bg-indigo-50 active:scale-[0.98] text-[13px] font-bold rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer mt-3 disabled:opacity-50 disabled:cursor-not-allowed disabled:active:scale-100"
                >
                  <Zap className="w-3.5 h-3.5" />
                  <span>{isCreateMode ? '保存后可校验连接' : '多路连接可用性测试'}</span>
                </button>
              </div>
            </div>

            {/* Step-by-step setup guide */}
            <div className="bg-emerald-50/20 border border-emerald-100/60 rounded-xl p-5 space-y-4 animate-in fade-in duration-300">
              <div className="flex items-center gap-2">
                <HelpCircle className="w-4 h-4 text-emerald-600" />
                <h4 className="text-[14px] font-bold text-gray-900 uppercase tracking-wide">Telegram 快速配置教程</h4>
              </div>
              <div className="space-y-4 text-[13px] text-gray-600 leading-relaxed font-sans">
                <div className="flex items-start gap-3">
                  <span className="w-5 h-5 rounded-full bg-emerald-600 text-white text-[10px] flex items-center justify-center font-bold font-mono shrink-0 select-none">1</span>
                  <p className="pt-0.5 font-medium text-gray-700">
                    在 Telegram 检索官方机器人 <strong className="text-gray-900 font-bold">@BotFather</strong>，发送 <code>/newbot</code> 指令配置名称，获取 <code>APIToken</code>。
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="w-5 h-5 rounded-full bg-emerald-600 text-white text-[10px] flex items-center justify-center font-bold font-mono shrink-0 select-none">2</span>
                  <p className="pt-0.5 font-medium text-gray-700">
                    向 <strong className="text-gray-900 font-bold">@userinfobot</strong> 发送消息，即可获知所有者 <code>Telegram User ID</code>。
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <span className="w-5 h-5 rounded-full bg-emerald-600 text-white text-[10px] flex items-center justify-center font-bold font-mono shrink-0 select-none">3</span>
                  <p className="pt-0.5 font-medium text-gray-700">
                    在左侧表单中配置 <code>所有者 ID</code> 及 <code>APIToken</code>，按需开启轮询服务后保存。
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

      {/* Validation modal dialogue */}
      {showValDialog && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setShowValDialog(false)}>
          <div
            className="w-full max-w-lg bg-white rounded-xl border border-[#e4e6ec] shadow-xl overflow-hidden animate-fadeIn"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b border-[#e4e6ec] bg-[#fbfbfe] flex justify-between items-center">
              <h3 className="font-bold text-gray-900 text-sm">双向连接压力校验 (Validate connection)</h3>
              <button onClick={() => setShowValDialog(false)} className="text-gray-400 hover:text-gray-600 focus:outline-none">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <p className="text-xs text-gray-500 leading-relaxed">
                此工具通过模拟发送 <code>getMe</code> 请求到 Telegram 官方服务器，验证该 Bot Token 密钥是否真实。
              </p>

              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-gray-700 block">
                  模拟临时密钥 (选填)
                </label>
                <input
                  type="text"
                  value={tempToken}
                  onChange={(e) => setTempToken(e.target.value)}
                  placeholder="留空则执行库中已保存密钥；在此填入不影响并不会保存新密钥"
                  className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono text-gray-800"
                />
              </div>

              {validationResult && (
                <div className={`p-4 rounded-lg text-xs leading-normal font-mono ${
                  validationSucceeded === true
                    ? 'bg-green-50 border border-green-200 text-green-700'
                    : 'bg-red-50 border border-red-200 text-red-700'
                }`}>
                  {validationResult}
                </div>
              )}

              <div className="flex justify-end gap-2 pt-4 border-t border-gray-100">
                <button
                  onClick={() => setShowValDialog(false)}
                  className="px-4 py-2 border border-gray-200 text-gray-500 rounded-lg text-xs font-semibold hover:bg-gray-50 cursor-pointer"
                >
                  关闭
                </button>
                <button
                  onClick={handleValidateConnection}
                  disabled={validating}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold flex items-center gap-2 cursor-pointer"
                >
                  {validating && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>启动校验联通测试</span>
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
}

// Custom internal icon component
function Workflow(props: any) {
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
      <rect width="8" height="8" x="3" y="3" rx="2" />
      <rect width="8" height="8" x="13" y="13" rx="2" />
      <path d="M11 7h2" />
      <path d="M7 11v2" />
      <path d="M11 13h2" />
      <path d="M17 11V7a2 2 0 0 0-2-2h-2" />
    </svg>
  );
}
