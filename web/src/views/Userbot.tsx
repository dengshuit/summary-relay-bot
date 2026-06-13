import React, { useEffect, useState } from 'react';
import {
  AlertCircle,
  Check,
  KeyRound,
  RefreshCw,
  Send,
  ShieldCheck,
  Smartphone,
  UserRound
} from 'lucide-react';
import { api } from '../api/client';
import { Userbot as UserbotConfig } from '../api/types';
import { useToast } from '../components/Toast';

type StatusTone = 'green' | 'amber' | 'red' | 'slate' | 'blue';

const authLabels: Record<string, { label: string; tone: StatusTone }> = {
  unconfigured: { label: '未授权', tone: 'slate' },
  code_sent: { label: '验证码已发送', tone: 'blue' },
  password_required: { label: '需要 2FA', tone: 'amber' },
  authorized: { label: '已授权', tone: 'green' },
  revoked: { label: '已失效', tone: 'red' },
  error: { label: '授权失败', tone: 'red' }
};

const runtimeLabels: Record<string, { label: string; tone: StatusTone }> = {
  stopped: { label: '已停止', tone: 'slate' },
  starting: { label: '启动中', tone: 'blue' },
  running: { label: '运行中', tone: 'green' },
  reloading: { label: '重载中', tone: 'blue' },
  failed: { label: '运行失败', tone: 'red' },
  disabled: { label: '已禁用', tone: 'slate' }
};

function toneClass(tone: StatusTone) {
  const map = {
    green: 'bg-emerald-50 text-emerald-700 border-emerald-100',
    amber: 'bg-amber-50 text-amber-700 border-amber-100',
    red: 'bg-rose-50 text-rose-700 border-rose-100',
    slate: 'bg-slate-50 text-slate-600 border-slate-200',
    blue: 'bg-sky-50 text-sky-700 border-sky-100'
  };
  return map[tone];
}

function SecretFlag({ label, configured }: { label: string; configured: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-gray-100 bg-gray-50/60 px-3 py-2">
      <span className="text-[12px] font-semibold text-gray-500">{label}</span>
      <span className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-bold ${
        configured
          ? 'border-emerald-100 bg-emerald-50 text-emerald-700'
          : 'border-slate-200 bg-white text-slate-500'
      }`}>
        {configured && <Check className="h-3 w-3" />}
        {configured ? '已配置' : '未配置'}
      </span>
    </div>
  );
}

export default function Userbot() {
  const showToast = useToast();
  const [userbot, setUserbot] = useState<UserbotConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sendingCode, setSendingCode] = useState(false);
  const [signingIn, setSigningIn] = useState(false);
  const [submittingPassword, setSubmittingPassword] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [name, setName] = useState('');
  const [apiId, setApiId] = useState('');
  const [apiHash, setApiHash] = useState('');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [proxyUrl, setProxyUrl] = useState('');
  const [enabled, setEnabled] = useState(true);
  const [code, setCode] = useState('');
  const [password, setPassword] = useState('');

  const isCreateMode = !userbot;
  const authStatus = authLabels[userbot?.auth_status || 'unconfigured'] || authLabels.unconfigured;
  const runtimeStatus = runtimeLabels[userbot?.runtime_status || 'disabled'] || runtimeLabels.disabled;

  const loadUserbot = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const response = await api.getUserbot();
      const item = response.item;
      setUserbot(item);
      if (item) {
        setName(item.name);
        setApiId(item.api_id ? String(item.api_id) : '');
        setEnabled(item.enabled);
      } else {
        setName('');
        setApiId('');
        setEnabled(true);
      }
      setApiHash('');
      setPhoneNumber('');
      setProxyUrl('');
      setCode('');
      setPassword('');
    } catch (err: any) {
      setErrorMsg(err.message || '读取 Userbot 配置失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUserbot();
  }, []);

  const handleSave = async (event: React.FormEvent) => {
    event.preventDefault();
    const trimmedName = name.trim();
    const trimmedApiId = apiId.trim();
    if (!trimmedName || !trimmedApiId) {
      showToast({ tone: 'error', title: '保存失败', detail: '名称和 API ID 不能为空。' });
      return;
    }
    if (isCreateMode && (!apiHash.trim() || !phoneNumber.trim())) {
      showToast({ tone: 'error', title: '保存失败', detail: '首次配置需要 API Hash 和手机号。' });
      return;
    }

    setSaving(true);
    try {
      const next = isCreateMode
        ? await api.createUserbot({
            name: trimmedName,
            api_id: trimmedApiId,
            api_hash: apiHash.trim(),
            phone_number: phoneNumber.trim(),
            proxy_url: proxyUrl.trim() || null,
            enabled
          })
        : await api.updateUserbot({
            id: userbot.id,
            name: trimmedName,
            api_id: trimmedApiId,
            api_hash: apiHash.trim() || undefined,
            phone_number: phoneNumber.trim() || undefined,
            proxy_url: proxyUrl.trim() || undefined,
            enabled
          });
      setUserbot(next);
      setApiHash('');
      setPhoneNumber('');
      setProxyUrl('');
      showToast({ tone: 'success', title: 'Userbot 配置已保存' });
    } catch (err: any) {
      showToast({ tone: 'error', title: '保存失败', detail: err.message || 'Userbot 配置保存失败。' });
    } finally {
      setSaving(false);
    }
  };

  const handleSendCode = async () => {
    if (!userbot) {
      showToast({ tone: 'error', title: '发送失败', detail: '请先保存 Userbot 配置。' });
      return;
    }
    setSendingCode(true);
    try {
      const next = await api.sendUserbotCode({ id: userbot.id });
      setUserbot(next);
      setCode('');
      setPassword('');
      showToast({ tone: 'success', title: '验证码请求已发送' });
    } catch (err: any) {
      showToast({ tone: 'error', title: '发送失败', detail: err.message || '验证码请求失败。' });
    } finally {
      setSendingCode(false);
    }
  };

  const handleSignIn = async () => {
    if (!userbot || !code.trim()) {
      showToast({ tone: 'error', title: '授权失败', detail: '请输入 Telegram 验证码。' });
      return;
    }
    setSigningIn(true);
    try {
      const next = await api.signInUserbot({ id: userbot.id, code: code.trim() });
      setUserbot(next);
      setCode('');
      showToast({
        tone: next.auth_status === 'password_required' ? 'warning' : 'success',
        title: next.auth_status === 'password_required' ? '需要 2FA 密码' : 'Userbot 已授权'
      });
    } catch (err: any) {
      showToast({ tone: 'error', title: '授权失败', detail: err.message || '验证码提交失败。' });
    } finally {
      setSigningIn(false);
    }
  };

  const handleSubmitPassword = async () => {
    if (!userbot || !password.trim()) {
      showToast({ tone: 'error', title: '提交失败', detail: '请输入 2FA 密码。' });
      return;
    }
    setSubmittingPassword(true);
    try {
      const next = await api.submitUserbotPassword({ id: userbot.id, password: password.trim() });
      setUserbot(next);
      setPassword('');
      showToast({ tone: 'success', title: '2FA 验证已完成' });
    } catch (err: any) {
      showToast({ tone: 'error', title: '提交失败', detail: err.message || '2FA 密码提交失败。' });
    } finally {
      setSubmittingPassword(false);
    }
  };

  if (loading && !userbot) {
    return (
      <div className="flex min-h-[400px] flex-col items-center justify-center gap-2">
        <RefreshCw className="h-6 w-6 animate-spin text-indigo-600" />
        <p className="text-sm text-gray-500">正在加载 Userbot 配置...</p>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-[96%] space-y-6 p-4 font-sans sm:p-6 xl:max-w-[93%] 2xl:max-w-[1590px]">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-[24px] font-semibold leading-none text-gray-900">Userbot 授权</h2>
        </div>
        <button
          type="button"
          onClick={loadUserbot}
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg border border-gray-200 bg-white px-3 text-xs font-semibold text-gray-600 hover:bg-gray-50"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          刷新
        </button>
      </div>

      {errorMsg && (
        <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-rose-600" />
          <p className="text-xs font-medium text-rose-700">{errorMsg}</p>
        </div>
      )}

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-[0_1px_2px_rgba(0,0,0,0.03)] lg:col-span-8">
          <div className="border-b border-gray-200 bg-[#fbfbfe] px-6 py-4">
            <span className="block text-[10px] font-mono uppercase tracking-wider text-indigo-600">Telethon control plane</span>
            <h3 className="mt-1 text-[16px] font-semibold text-gray-900">
              {isCreateMode ? '新增 Userbot 配置' : '授权材料设置'}
            </h3>
          </div>

          <form onSubmit={handleSave} className="space-y-6 p-6">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="block text-[15px] font-semibold text-gray-700">名称</label>
                <input
                  type="text"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  className="h-10 w-full rounded-lg border border-gray-200 px-3.5 py-2.5 text-[15px] text-gray-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
              <div className="space-y-2">
                <label className="block text-[15px] font-semibold text-gray-700">API ID</label>
                <input
                  type="number"
                  value={apiId}
                  onChange={(event) => setApiId(event.target.value)}
                  className="h-10 w-full rounded-lg border border-gray-200 px-3.5 py-2.5 font-mono text-[15px] text-gray-800 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <label className="block text-[15px] font-semibold text-gray-700">
                  {isCreateMode ? 'API Hash' : 'API Hash 更换'}
                </label>
                <input
                  type="password"
                  value={apiHash}
                  onChange={(event) => setApiHash(event.target.value)}
                  placeholder={userbot?.secrets.api_hash.configured ? '输入新值以更换' : ''}
                  className="h-10 w-full rounded-lg border border-gray-200 px-3.5 py-2.5 font-mono text-[15px] text-gray-800 placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
              <div className="space-y-2">
                <label className="block text-[15px] font-semibold text-gray-700">
                  {isCreateMode ? '手机号' : '手机号更换'}
                </label>
                <input
                  type="password"
                  value={phoneNumber}
                  onChange={(event) => setPhoneNumber(event.target.value)}
                  placeholder={userbot?.phone_number_redacted ? '输入新手机号以更换' : ''}
                  className="h-10 w-full rounded-lg border border-gray-200 px-3.5 py-2.5 font-mono text-[15px] text-gray-800 placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="block text-[15px] font-semibold text-gray-700">代理 URL 更换</label>
              <input
                type="password"
                value={proxyUrl}
                onChange={(event) => setProxyUrl(event.target.value)}
                placeholder={userbot?.secrets.proxy_url.configured ? '输入新代理 URL 以更换' : 'socks5://127.0.0.1:1080'}
                className="h-10 w-full rounded-lg border border-gray-200 px-3.5 py-2.5 font-mono text-[15px] text-gray-800 placeholder:text-gray-400 focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
              />
            </div>

            <div className="flex items-center justify-between border-t border-gray-100 pt-4">
              <span className="block text-[15px] font-semibold text-gray-850">启用当前 Userbot</span>
              <label className="relative inline-flex cursor-pointer items-center">
                <input
                  type="checkbox"
                  checked={enabled}
                  onChange={(event) => setEnabled(event.target.checked)}
                  className="peer sr-only"
                />
                <div className="h-5 w-9 rounded-full bg-gray-200 after:absolute after:left-[2px] after:top-[2px] after:h-4 after:w-4 after:rounded-full after:border after:border-gray-300 after:bg-white after:transition-all after:content-[''] peer-checked:bg-indigo-600 peer-checked:after:translate-x-full peer-checked:after:border-white" />
              </label>
            </div>

            <div className="rounded-lg border border-indigo-100/80 bg-indigo-50/25 p-4">
              <div className="mb-3 flex items-center gap-2">
                <KeyRound className="h-4 w-4 text-indigo-600" />
                <h4 className="text-[13px] font-bold text-gray-900">获取 API ID / API Hash</h4>
              </div>
              <ol className="space-y-3 text-[13px] leading-relaxed text-gray-600">
                <li className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 font-mono text-[10px] font-bold text-white">
                    1
                  </span>
                  <span>
                    打开{' '}
                    <a
                      href="https://my.telegram.org"
                      target="_blank"
                      rel="noreferrer"
                      className="font-semibold text-indigo-700 underline decoration-indigo-200 underline-offset-2 hover:text-indigo-800"
                    >
                      my.telegram.org
                    </a>
                    ，进入 <span className="font-semibold text-gray-800">API development tools</span>。
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 font-mono text-[10px] font-bold text-white">
                    2
                  </span>
                  <span>创建一个 Telegram application，提交后页面会生成这组应用凭据。</span>
                </li>
                <li className="flex gap-3">
                  <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-600 font-mono text-[10px] font-bold text-white">
                    3
                  </span>
                  <span>
                    复制 <code className="font-mono text-gray-900">api_id</code> 和{' '}
                    <code className="font-mono text-gray-900">api_hash</code> 填入上方对应字段；{' '}
                    <code className="font-mono text-gray-900">api_hash</code> 按密钥保存，不要公开。
                  </span>
                </li>
              </ol>
            </div>

            <div className="flex items-center justify-end gap-3 border-t border-gray-100 pt-4">
              <button
                type="button"
                onClick={loadUserbot}
                className="flex h-10 items-center justify-center rounded-lg border border-gray-250 px-4 text-xs font-semibold text-gray-500 hover:bg-gray-50"
              >
                重置
              </button>
              <button
                type="submit"
                disabled={saving}
                className="flex h-10 items-center justify-center gap-2 rounded-lg bg-indigo-600 px-5 text-xs font-semibold text-white shadow-sm hover:bg-indigo-700 disabled:opacity-50"
              >
                {saving && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                保存配置
              </button>
            </div>
          </form>
        </div>

        <div className="space-y-6 lg:col-span-4">
          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
            <div className="border-b border-gray-100 bg-slate-50/50 px-5 py-4">
              <h3 className="text-[14px] font-bold text-gray-800">授权状态</h3>
            </div>
            <div className="space-y-4 p-5 text-[14px]">
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-500">授权</span>
                <span className={`rounded border px-2 py-0.5 text-[11px] font-bold ${toneClass(authStatus.tone)}`}>
                  {authStatus.label}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-500">运行时</span>
                <span className={`rounded border px-2 py-0.5 text-[11px] font-bold ${toneClass(runtimeStatus.tone)}`}>
                  {runtimeStatus.label}
                </span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                <SecretFlag label="API Hash" configured={!!userbot?.secrets.api_hash.configured} />
                <SecretFlag label="手机号" configured={!!userbot?.secrets.phone_number.configured} />
                <SecretFlag label="Session" configured={!!userbot?.secrets.session.configured} />
                <SecretFlag label="代理" configured={!!userbot?.secrets.proxy_url.configured} />
              </div>

              <div className="rounded-lg border border-gray-100 bg-gray-50/60 p-3">
                <div className="mb-2 flex items-center gap-2 text-[11px] font-bold uppercase tracking-widest text-gray-400">
                  <UserRound className="h-3.5 w-3.5" />
                  Telegram identity
                </div>
                <div className="grid grid-cols-2 gap-2 font-mono text-[12px] text-gray-600">
                  <div>
                    <span className="block text-[9px] font-bold uppercase text-gray-400">User ID</span>
                    <strong className="mt-0.5 block truncate text-gray-800">{userbot?.telegram_user_id || '未知'}</strong>
                  </div>
                  <div>
                    <span className="block text-[9px] font-bold uppercase text-gray-400">Username</span>
                    <strong className="mt-0.5 block truncate text-gray-800">
                      {userbot?.telegram_username ? `@${userbot.telegram_username}` : '待授权'}
                    </strong>
                  </div>
                </div>
              </div>

              {userbot?.last_error_message && (
                <div className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-xs text-rose-700">
                  <span className="font-bold">{userbot.last_error_type || 'error'}: </span>
                  {userbot.last_error_message}
                </div>
              )}
            </div>
          </div>

          <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-[0_1px_2px_rgba(0,0,0,0.03)]">
            <div className="border-b border-gray-100 bg-[#fbfbfe] px-5 py-4">
              <h3 className="text-[14px] font-bold text-gray-800">登录授权</h3>
            </div>
            <div className="space-y-4 p-5">
              <button
                type="button"
                disabled={!userbot || sendingCode}
                onClick={handleSendCode}
                className="flex h-10 w-full items-center justify-center gap-2 rounded-lg border border-sky-200 bg-sky-50/40 text-[13px] font-bold text-sky-700 hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {sendingCode ? <RefreshCw className="h-3.5 w-3.5 animate-spin" /> : <Send className="h-3.5 w-3.5" />}
                发送验证码
              </button>

              <div className="space-y-2">
                <label className="block text-xs font-semibold text-gray-700">验证码</label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={code}
                    onChange={(event) => setCode(event.target.value)}
                    className="h-10 min-w-0 flex-1 rounded-lg border border-gray-200 px-3 font-mono text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100"
                  />
                  <button
                    type="button"
                    onClick={handleSignIn}
                    disabled={!userbot || signingIn}
                    className="flex h-10 w-24 shrink-0 items-center justify-center gap-1.5 rounded-lg bg-indigo-600 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-50"
                  >
                    {signingIn && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                    提交
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <label className="block text-xs font-semibold text-gray-700">2FA 密码</label>
                <div className="flex gap-2">
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    disabled={userbot?.auth_status !== 'password_required'}
                    className="h-10 min-w-0 flex-1 rounded-lg border border-gray-200 px-3 font-mono text-sm focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:bg-gray-50 disabled:text-gray-400"
                  />
                  <button
                    type="button"
                    onClick={handleSubmitPassword}
                    disabled={!userbot || userbot.auth_status !== 'password_required' || submittingPassword}
                    className="flex h-10 w-24 shrink-0 items-center justify-center gap-1.5 rounded-lg border border-amber-200 bg-amber-50 text-xs font-semibold text-amber-700 hover:bg-amber-100 disabled:opacity-50"
                  >
                    {submittingPassword && <RefreshCw className="h-3.5 w-3.5 animate-spin" />}
                    验证
                  </button>
                </div>
              </div>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <Smartphone className="mb-2 h-4 w-4 text-indigo-600" />
              <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Config</p>
              <p className="mt-1 text-xs font-semibold text-gray-800">{userbot ? 'ready' : 'empty'}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <KeyRound className="mb-2 h-4 w-4 text-sky-600" />
              <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Auth</p>
              <p className="mt-1 text-xs font-semibold text-gray-800">{authStatus.label}</p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-3">
              <ShieldCheck className="mb-2 h-4 w-4 text-emerald-600" />
              <p className="text-[11px] font-bold uppercase tracking-widest text-gray-400">Session</p>
              <p className="mt-1 text-xs font-semibold text-gray-800">
                {userbot?.secrets.session.configured ? 'stored' : 'none'}
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
