import React, { useState } from 'react';
import {
  Bot,
  Settings,
  Workflow,
  Users,
  Plus,
  Info,
  AlertCircle,
  CheckCircle2,
  X,
  Play,
  RotateCw,
  LogOut,
  User,
  Activity,
  ArrowRight
} from 'lucide-react';

export default function ComponentReference() {
  const [toggleVal, setToggleVal] = useState(true);
  const [inputText, setInputText] = useState('这是预置的校验文案');
  const [selectVal, setSelectVal] = useState('deepseek-r1');
  const [showDemoModal, setShowDemoModal] = useState(false);

  return (
    <div className="space-y-8 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* Page Title */}
      <div>
        <div className="inline-block px-2 py-0.5 bg-indigo-50 border border-indigo-100 rounded text-[10px] font-mono text-indigo-600 uppercase tracking-wider">
          Internal Dev Reference Map
        </div>
        <h2 className="text-xl font-bold text-gray-900 mt-1 cursor-default">组件规范与设计系统 (WebUI Styleguide)</h2>
        <p className="text-xs text-gray-400 mt-1">
          当前专区用于管理员及设计师复查原子组件的圆角、行高、文字色阶对比度以及微动作反馈。
        </p>
      </div>

      {/* Color Tokens Swatch */}
      <section className="space-y-4">
        <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">1. 状态调色板及核心 Tokens (Visual Tokens)</h3>
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <div className="space-y-1.5">
            <div className="h-14 w-full bg-[#f6f7fb] rounded-lg border border-[#e4e6ec] shadow-inner"></div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">系统背景 (Canvas)</span>
              <code className="text-[10px] text-gray-400 font-mono">#f6f7fb</code>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="h-14 w-full bg-white rounded-lg border border-[#e4e6ec] shadow-sm"></div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">主体容器 (Surface)</span>
              <code className="text-[10px] text-gray-400 font-mono">#ffffff</code>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="h-14 w-full bg-[#7C3AED] rounded-lg shadow-sm"></div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">核心主色 (Primary Violet)</span>
              <code className="text-[10px] text-gray-400 font-mono">#7C3AED</code>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="h-14 w-full bg-[#7b2cbf] rounded-lg shadow-sm"></div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">高阶渐变色 (Purple Accent)</span>
              <code className="text-[10px] text-gray-400 font-mono">#7b2cbf</code>
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="h-14 w-full border border-dashed border-[#e4e6ec] rounded-lg flex items-center justify-center font-bold text-indigo-200">
              Border-Ring
            </div>
            <div>
              <span className="text-xs font-semibold text-gray-700 block">通用线框 (Border-Light)</span>
              <code className="text-[10px] text-gray-400 font-mono">#e4e6ec</code>
            </div>
          </div>
        </div>
      </section>

      {/* Grid: Buttons vs Form Controls */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Buttons section */}
        <section className="space-y-4">
          <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">2. 按钮类型及反馈动作</h3>

          <div className="space-y-3">
            <div className="flex flex-wrap gap-2">
              <button className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-xs font-semibold rounded-lg cursor-pointer shadow-sm transition-all">
                Primary Button
              </button>

              <button className="px-4 py-2 border border-indigo-200 text-indigo-600 hover:bg-indigo-50/50 text-xs font-semibold rounded-lg cursor-pointer transition-all">
                Interactive Outline
              </button>

              <button className="px-4 py-2 border border-[#e4e6ec] hover:bg-gray-50 text-gray-600 text-xs font-semibold rounded-lg cursor-pointer transition-all">
                Secondary Neutral
              </button>

              <button className="px-4 py-2 bg-red-600 hover:bg-red-700 text-white text-xs font-semibold rounded-lg cursor-pointer transition-all">
                Danger Alert Action
              </button>
            </div>

            <p className="text-[11px] text-gray-400">带 Lucide 前置/后置矢量图标示例：</p>
            <div className="flex flex-wrap gap-2">
              <button className="px-3.5 py-1.5 bg-indigo-600 text-white text-xs font-semibold rounded-lg flex items-center gap-1.5 cursor-pointer">
                <Plus className="w-3.5 h-3.5" />
                <span>新增 Bot 实例</span>
              </button>
              <button className="px-3.5 py-1.5 border border-indigo-200 text-indigo-600 hover:bg-indigo-50/50 text-xs font-semibold rounded-lg flex items-center gap-1.5 cursor-pointer">
                <span>进入配置详情</span>
                <ArrowRight className="w-3.5 h-3.5" />
              </button>
              <button className="px-3 py-1.5 border border-gray-200 text-gray-500 hover:bg-gray-50 rounded-lg flex items-center gap-1 cursor-pointer">
                <RotateCw className="w-3.5 h-3.5 text-gray-400" />
              </button>
            </div>
          </div>
        </section>

        {/* Inputs & form fields */}
        <section className="space-y-4">
          <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">3. 基础表单输入字段 (Forms)</h3>

          <div className="space-y-4">
            {/* Standard Text */}
            <div className="space-y-1">
              <label className="text-xs font-semibold text-gray-700 block">单行文本输入器</label>
              <input
                type="text"
                value={inputText}
                onChange={(e) => setInputText(e.target.value)}
                className="w-full px-3 py-2 border border-[#e4e6ec] bg-white text-xs rounded-lg focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100 focus:outline-none"
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              {/* Select */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-700 block">下拉列表器</label>
                <select
                  value={selectVal}
                  onChange={(e) => setSelectVal(e.target.value)}
                  className="w-full px-3 py-2 border border-[#e4e6ec] bg-white text-xs rounded-lg focus:outline-none"
                >
                  <option value="openai">OpenAI GPT-4o</option>
                  <option value="deepseek-r1">DeepSeek Reasoner R1</option>
                  <option value="claude-3.5-sonnet">Claude 3.5 Sonnet</option>
                </select>
              </div>

              {/* Toggle Switch */}
              <div className="space-y-1">
                <label className="text-xs font-semibold text-gray-75w700 block">单点开关</label>
                <div className="flex items-center justify-between h-[38px] px-3 bg-[#fafafa] border border-gray-100 rounded-lg">
                  <span className="text-[11px] text-gray-500">
                    {toggleVal ? '已开启自动' : '已选择静音'}
                  </span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={toggleVal}
                      onChange={(e) => setToggleVal(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-9 h-5 bg-gray-200 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border wave after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </section>
      </div>

      {/* Info Boxes & Modals Demo */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Info alerts */}
        <section className="space-y-4">
          <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">4. 场景状态提示横幅 (Banners & Alerts)</h3>

          <div className="space-y-3">
            {/* Info alert */}
            <div className="p-3.5 bg-blue-50 border border-blue-200 text-blue-800 rounded-lg flex gap-3 text-xs">
              <Info className="w-5 h-5 text-blue-500 shrink-0 mt-0.5" />
              <div>
                <strong className="font-bold text-blue-900 block mb-0.5">普通情况：多通道发现中</strong>
                把 Bot 邀请入群并给予消息查看权限，聊天产生时就会自动生成新条目在该面板中。
              </div>
            </div>

            {/* Error alert */}
            <div className="p-3.5 bg-red-50 border border-red-200 text-red-800 rounded-lg flex gap-3 text-xs">
              <AlertCircle className="w-5 h-5 text-red-500 shrink-0 mt-0.5" />
              <div>
                <strong className="font-bold text-red-900 block mb-0.5">异常拦截：授权失败</strong>
                您输入的 WEBUI_ADMIN_TOKEN 秘钥不匹配，请复查配置文件以修正。
              </div>
            </div>

            {/* Warn Alert */}
            <div className="p-3.5 bg-amber-50 border border-amber-200 text-amber-800 rounded-lg flex gap-3 text-xs">
              <AlertCircle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
              <div>
                <strong className="font-bold text-amber-900 block mb-0.5">配置 pending 提示：</strong>
                密钥更换需要重启轮询守护进程以刷新工作台状态。
              </div>
            </div>
          </div>
        </section>

        {/* Modal activation preview */}
        <section className="space-y-4">
          <h3 className="text-sm font-bold text-gray-800 border-b border-gray-100 pb-2">5. 对话窗口与浮层体系 (Modal Overlay)</h3>

          <div className="p-6 bg-white border border-[#e4e6ec] rounded-xl flex flex-col items-center justify-center min-h-[160px] gap-2 shadow-inner">
            <p className="text-xs text-gray-500">点击按钮查看对话框遮罩行为：</p>
            <button
              onClick={() => setShowDemoModal(true)}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer shadow-sm flex items-center gap-1"
            >
              <Workflow className="w-3.5 h-3.5" />
              <span>打开测试浮层 Overlay</span>
            </button>
          </div>
        </section>
      </div>

      {/* Demo overlay modal */}
      {showDemoModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setShowDemoModal(false)}>
          <div
            className="w-full max-w-md bg-white rounded-xl border border-[#e4e6ec] shadow-xl overflow-hidden animate-fadeIn"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-6 py-4 border-b border-[#e4e6ec] bg-[#fbfbfe] flex justify-between items-center">
              <h3 className="font-bold text-gray-900 text-sm">Visual Modal Showcase</h3>
              <button onClick={() => setShowDemoModal(false)} className="text-gray-400 hover:text-gray-600 focus:outline-none">
                <X className="w-4 h-4" />
              </button>
            </div>
            <div className="p-6 space-y-3 text-xs text-gray-600 leading-relaxed">
              <p>这是一个原子模态展示窗体，它会优雅、居中地漂浮在平台主体之上，并将周边页面施加柔和的 <code>backdrop-blur</code> 或 <code>bg-black/40</code> 黑影阻断点击。</p>
              <p>可以任意摆放表单，底层附带圆角度对齐。</p>
            </div>
            <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2 bg-[#fafafa]">
              <button
                onClick={() => setShowDemoModal(false)}
                className="px-4 py-2 border border-gray-200 text-gray-500 rounded-lg text-xs font-semibold hover:bg-gray-50 cursor-pointer"
              >
                我知道了
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
