import React, { useState } from 'react';
import { api } from '../api/client';
import { ShieldAlert, LogIn, Loader2 } from 'lucide-react';

interface LoginProps {
  onLoginSuccess: (token: string) => void;
}

export default function Login({ onLoginSuccess }: LoginProps) {
  const [token, setToken] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!token.trim()) return;

    setLoading(true);
    setErrorMsg(null);

    try {
      await api.login(token.trim());
      onLoginSuccess(token.trim());
    } catch (err: any) {
      setErrorMsg('认证失败');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-[#f6f7fb] p-6 selection:bg-indigo-100 font-sans">
      <div className="w-full max-w-[420px] bg-white rounded-xl border border-[#e4e6ec] p-8 shadow-sm">
        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-indigo-600 flex items-center justify-center text-white font-bold text-xl mb-4 shadow-sm">
            SR
          </div>
          <h1 className="text-xl font-bold text-gray-900 tracking-tight">Summary Relay 配置中心</h1>
          <p className="text-xs text-gray-500 mt-2">Single-Admin Bot Operational Dashboard</p>
        </div>

        {/* Error notification banner */}
        {errorMsg && (
          <div className="mb-6 p-3 bg-red-50 border border-red-200 rounded-lg flex items-center gap-3">
            <ShieldAlert className="w-5 h-5 text-red-500 shrink-0" />
            <div className="text-xs text-red-700 font-medium">
              {errorMsg}：Token 校验失败，请检查配置。
            </div>
          </div>
        )}

        {/* Credentials Form */}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div className="space-y-2">
            <label className="text-xs font-semibold text-gray-700 block">
              管理 Token
            </label>
            <div className="relative">
              <input
                type="password"
                required
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="请输入 WEBUI_ADMIN_TOKEN 秘钥"
                disabled={loading}
                className="w-full px-4 py-2.5 rounded-lg border border-[#e4e6ec] text-sm text-gray-900 placeholder:text-gray-400 bg-white shadow-inner focus:border-indigo-500 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:bg-gray-50 disabled:text-gray-400 font-mono transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading || !token.trim()}
            className="w-full py-2.5 rounded-lg text-white font-medium text-sm transition-all flex items-center justify-center gap-2 cursor-pointer bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-100 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin" />
            ) : (
              <LogIn className="w-4 h-4" />
            )}
            <span>登录</span>
          </button>
        </form>

        {/* Help footnotes */}
        <div className="mt-8 pt-4 border-t border-gray-100 text-center">
          <p className="text-[11px] text-gray-400 leading-relaxed">
            安全起见，您的登录状态只会保留在当前浏览器窗口中，关闭窗口后会自动清除。
          </p>
          <p className="text-[10px] text-indigo-500 font-mono mt-3 select-all">
            本地默认开发 Token: <span className="font-semibold bg-indigo-50 px-1 py-0.5 rounded">admin-token-123</span>
          </p>
        </div>
      </div>
    </div>
  );
}
