import React, { useEffect, useState } from 'react';
import { api } from '../api/client';
import { LLMProvider, SummaryProfile } from '../api/types';
import {
  Cpu,
  Settings,
  Plus,
  HelpCircle,
  RefreshCw,
  Check,
  X,
  Play,
  AlertCircle,
  Gauge,
  Code,
  CheckCircle,
  Hash
} from 'lucide-react';
import CustomSelect from '../components/CustomSelect';

const TYPE_PRESETS: Record<string, string[]> = {
  openai: [
    'gpt-4o-mini',
    'gpt-4o',
    'o1-mini',
    'o1-preview',
    'gpt-4-turbo',
    'gpt-3.5-turbo'
  ],
  anthropic: [
    'claude-3-5-sonnet-latest',
    'claude-3-5-haiku-latest',
    'claude-3-opus-20240229',
    'claude-3-sonnet-20240229'
  ],
  openai_compatible: [
    'deepseek-chat',
    'deepseek-coder',
    'gemini-2.5-flash',
    'gemini-2.5-pro',
    'gemini-1.5-flash',
    'qwen-turbo',
    'qwen-max',
    'qwen-plus',
    'llama3-70b',
    'mistral-large'
  ]
};

export default function Engine() {
  const [activeTab, setActiveTab] = useState<'provider' | 'profile'>('provider');
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [profiles, setProfiles] = useState<SummaryProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Modals visibility
  const [providerModal, setProviderModal] = useState<boolean>(false);
  const [profileModal, setProfileModal] = useState<boolean>(false);

  // Edit provider fields
  const [editingProviderId, setEditingProviderId] = useState<string | null>(null);
  const [provName, setProvName] = useState('');
  const [provType, setProvType] = useState<'openai' | 'anthropic' | 'openai_compatible'>('openai');
  const [provBaseUrl, setProvBaseUrl] = useState('');
  const [provApiKey, setProvApiKey] = useState('');
  const [provEnabled, setProvEnabled] = useState(true);

  // Upstream models list, tags list, and manual inputs
  const [provSupportedModels, setProvSupportedModels] = useState<string[]>([]);
  const [newModelInput, setNewModelInput] = useState('');
  const [fetchingModels, setFetchingModels] = useState(false);

  // Upstream fetch checkboxes overlays
  const [upstreamFetchModal, setUpstreamFetchModal] = useState(false);
  const [fetchedModelsList, setFetchedModelsList] = useState<string[]>([]);
  const [selectedUpstreamModels, setSelectedUpstreamModels] = useState<string[]>([]);

  // Edit profile fields
  const [editingProfileId, setEditingProfileId] = useState<string | null>(null);
  const [profName, setProfName] = useState('');
  const [profProviderId, setProfProviderId] = useState('');
  const [profModel, setProfModel] = useState('');
  const [profPromptVersion, setProfPromptVersion] = useState('v1');
  const [profSystemPrompt, setProfSystemPrompt] = useState('');
  const [profTemp, setProfTemp] = useState(0.5);
  const [profTokens, setProfTokens] = useState(2500);
  const [profEnabled, setProfEnabled] = useState(true);
  const [profDefault, setProfDefault] = useState(false);

  // Dynamic models of chosen profile provider
  const [profileModels, setProfileModels] = useState<string[]>([]);
  const [loadingProfileModels, setLoadingProfileModels] = useState(false);

  // Action states
  const [testingId, setTestingId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [confirmModal, setConfirmModal] = useState<{
    ownerId: string;
    type: 'provider' | 'profile';
    name: string;
  } | null>(null);

  const handleConfirmDelete = async () => {
    if (!confirmModal) return;
    const { ownerId, type } = confirmModal;
    setSaving(true);
    try {
      if (type === 'provider') {
        await api.deleteProvider(ownerId);
      } else {
        await api.deleteProfile(ownerId);
      }
      setConfirmModal(null);
      await fetchEngineData();
    } catch (err: any) {
      alert('删除失败: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const fetchEngineData = async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const provs = await api.getProviders();
      const profs = await api.getProfiles();
      setProviders(provs);
      setProfiles(profs);
    } catch (err: any) {
      setErrorMsg(err.message || '获取摘要引擎数据失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEngineData();
  }, []);

  // Sync provSupportedModels when providerModal or provType changes
  useEffect(() => {
    if (providerModal && !editingProviderId) {
      const list = TYPE_PRESETS[provType] || TYPE_PRESETS.openai_compatible;
      setProvSupportedModels(list);
    }
  }, [provType, providerModal, editingProviderId]);

  // Sync profileModels when profProviderId changes in profile modal
  useEffect(() => {
    if (profileModal && profProviderId) {
      const loadProfileModels = async () => {
        setLoadingProfileModels(true);
        try {
          const res = await api.getProviderModels(profProviderId);
          if (res.success && res.models) {
            setProfileModels(res.models);
            if (res.models.length > 0) {
              if (!profModel || !res.models.includes(profModel)) {
                setProfModel(res.models[0]);
              }
            } else {
              setProfModel('');
            }
          }
        } catch (e) {
          const activeProv = providers.find(p => String(p.id) === profProviderId);
          if (activeProv) {
            const list = activeProv.models || TYPE_PRESETS[activeProv.provider_type] || TYPE_PRESETS.openai_compatible;
            setProfileModels(list);
            if (list.length > 0) {
              if (!profModel || !list.includes(profModel)) {
                setProfModel(list[0]);
              }
            } else {
              setProfModel('');
            }
          }
        } finally {
          setLoadingProfileModels(false);
        }
      };
      loadProfileModels();
    }
  }, [profProviderId, profileModal, providers]);

  const handleAddManualModel = () => {
    const val = newModelInput.trim();
    if (!val) return;
    if (!provSupportedModels.includes(val)) {
      const newList = [...provSupportedModels, val];
      setProvSupportedModels(newList);
    }
    setNewModelInput('');
  };

  const handleRemoveSupportedModel = (modelToRemove: string) => {
    const newList = provSupportedModels.filter(m => m !== modelToRemove);
    setProvSupportedModels(newList);
  };

  const handleTriggerFetchUpstream = async () => {
    setFetchingModels(true);
    try {
      const res = await api.fetchUpstreamModels({
        provider_type: provType,
        base_url: provBaseUrl || undefined,
        api_key: provApiKey || undefined
      });
      if (res.success && res.models) {
        setFetchedModelsList(res.models);
        // Default to checking all models
        setSelectedUpstreamModels(res.models);
        setUpstreamFetchModal(true);
      } else {
        alert('无法获取上游模型数据.');
      }
    } catch (err: any) {
      alert('从接口拉取上游模型失败: ' + err.message);
    } finally {
      setFetchingModels(false);
    }
  };

  const handleConfirmImportUpstream = () => {
    const added = selectedUpstreamModels.filter(m => !provSupportedModels.includes(m));
    if (added.length > 0) {
      const mergedList = [...provSupportedModels, ...added];
      setProvSupportedModels(mergedList);
    }
    setUpstreamFetchModal(false);
  };

  // Provider operations
  const openAddProvider = () => {
    setEditingProviderId(null);
    setProvName('');
    setProvType('openai');
    setProvBaseUrl('');
    setProvApiKey('');

    const defaults = TYPE_PRESETS['openai'];
    setProvSupportedModels(defaults);

    setProvEnabled(true);
    setProviderModal(true);
  };

  const openEditProvider = (p: LLMProvider) => {
    setEditingProviderId(String(p.id));
    setProvName(p.name);
    setProvType(p.provider_type);
    setProvBaseUrl(p.base_url || '');
    setProvApiKey(''); // replacement-only

    const list = p.models && p.models.length > 0 ? p.models : (TYPE_PRESETS[p.provider_type] || TYPE_PRESETS.openai_compatible);
    setProvSupportedModels(list);

    setProvEnabled(p.enabled);
    setProviderModal(true);
  };

  const handleToggleProviderEnabled = async (p: LLMProvider) => {
    try {
      await api.updateProvider(p.id, { enabled: !p.enabled });
      await fetchEngineData();
    } catch (err: any) {
      alert('修改 Provider 状态失败: ' + err.message);
    }
  };

  const handleSaveProvider = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!provName.trim()) return;
    if (provSupportedModels.length === 0) {
      alert('请确保模型列表不为空！');
      return;
    }

    setSaving(true);
    try {
      const payload: any = {
        name: provName,
        provider_type: provType,
        base_url: provBaseUrl || null,
        default_model: provSupportedModels[0] || '',
        enabled: provEnabled,
        models: provSupportedModels
      };
      if (provApiKey.trim()) payload.api_key = provApiKey;

      if (editingProviderId) {
        await api.updateProvider(editingProviderId, payload);
      } else {
        await api.createProvider(payload);
      }
      setProviderModal(false);
      await fetchEngineData();
    } catch (err: any) {
      alert('保存渠道失败: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleTestProvider = async (id: number | string) => {
    setTestingId(String(id));
    try {
      const res = await api.testProvider(id);
      alert('接口测试成功！\n' + res.detail);
      await fetchEngineData();
    } catch (err: any) {
      alert('连接测试失败: ' + err.message);
    } finally {
      setTestingId(null);
    }
  };

  // Profile operations
  const openAddProfile = () => {
    if (providers.length === 0) {
      alert('请确保当前在 LLM Provider 面板下已至少存在一个可用的连接！');
      return;
    }
    setEditingProfileId(null);
    setProfName('');
    const firstProv = providers[0];
    setProfProviderId(firstProv ? String(firstProv.id) : '');
    setProfModel(firstProv ? (firstProv.models?.[0] || TYPE_PRESETS[firstProv.provider_type]?.[0] || '') : '');
    setProfPromptVersion('v1');
    setProfSystemPrompt('');
    setProfTemp(0.5);
    setProfTokens(2500);
    setProfEnabled(true);
    setProfDefault(false);
    setProfileModal(true);
  };

  const openEditProfile = (p: SummaryProfile) => {
    setEditingProfileId(String(p.id));
    setProfName(p.name);
    setProfProviderId(String(p.llm_provider_id));
    setProfModel(p.model || p.effective_model || '');
    setProfPromptVersion(p.prompt_version || 'v1');
    setProfSystemPrompt(p.system_prompt || '');
    setProfTemp(p.temperature ?? 0.5);
    setProfTokens(p.max_output_tokens ?? 2500);
    setProfEnabled(p.enabled);
    setProfDefault(p.is_default);
    setProfileModal(true);
  };

  const handleSaveProfile = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!profName.trim()) return;
    if (!profModel) {
      alert('请指定一个必填的执行模型！');
      return;
    }

    // Confirm switch default
    if (profDefault) {
      const currentDefault = profiles.find(p => p.is_default && String(p.id) !== editingProfileId);
      if (currentDefault) {
        const confirmDefault = window.confirm(
          `已存在默认摘要 Profile "${currentDefault.name}"。此操作会撤销已有默认关系并将 "${profName}" 定为全局缺省策略。确认设为默认吗？`
        );
        if (!confirmDefault) return;
      }
    }

    setSaving(true);
    try {
      const payload: any = {
        name: profName,
        llm_provider_id: Number(profProviderId),
        model: profModel,
        prompt_version: profPromptVersion,
        system_prompt: profSystemPrompt || null,
        temperature: profTemp,
        max_output_tokens: profTokens,
        enabled: profEnabled,
        is_default: profDefault
      };

      if (editingProfileId) {
        await api.updateProfile(editingProfileId, payload);
      } else {
        await api.createProfile(payload);
      }
      setProfileModal(false);
      await fetchEngineData();
    } catch (err: any) {
      alert('保存 Summary Profile 失败: ' + err.message);
    } finally {
      setSaving(false);
    }
  };

  const handleSetDefaultProfile = async (id: number | string, name: string) => {
    const confirmDefault = window.confirm(`是否确信将 "${name}" 绑定为全局缺省默认摘要处理策略？`);
    if (!confirmDefault) return;

    try {
      await api.setDefaultProfile(id);
      await fetchEngineData();
    } catch (err: any) {
      alert('设为默认模板失败: ' + err.message);
    }
  };

  const handleDeleteProvider = (id: number | string, name: string) => {
    setConfirmModal({ ownerId: String(id), type: 'provider', name: name });
  };

  const handleDeleteProfile = (id: number | string, name: string) => {
    setConfirmModal({ ownerId: String(id), type: 'profile', name: name });
  };

  if (loading && providers.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[400px] gap-2">
        <RefreshCw className="w-6 h-6 text-indigo-600 animate-spin" />
        <p className="text-sm text-gray-500">正在获取模型驱动与预设框架...</p>
      </div>
    );
  }

  return (
    <div className="space-y-6 w-full max-w-[96%] xl:max-w-[93%] 2xl:max-w-[1590px] mx-auto p-4 sm:p-6 font-sans">
      {/* Navigation Sub-Tabs */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 border-b border-gray-100 pb-4">
        <div className="bg-gray-100 p-1 rounded-xl flex items-center gap-1 select-none border border-gray-200/40 shadow-inner">
          <button
            onClick={() => setActiveTab('provider')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all duration-200 cursor-pointer ${
              activeTab === 'provider'
                ? 'bg-white text-indigo-700 shadow-md border border-gray-200/10'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <Cpu className="w-3.5 h-3.5" />
            LLM 渠道配置
          </button>
          <button
            onClick={() => setActiveTab('profile')}
            className={`flex items-center gap-2 px-5 py-2.5 rounded-lg text-xs font-bold tracking-wider transition-all duration-200 cursor-pointer ${
              activeTab === 'profile'
                ? 'bg-white text-indigo-700 shadow-md border border-gray-200/10'
                : 'text-gray-500 hover:text-gray-900'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            总结模板配置
          </button>
        </div>

        {activeTab === 'provider' ? (
          <button
            onClick={openAddProvider}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-[14px] font-semibold rounded-lg shrink-0 cursor-pointer shadow-sm mb-2 h-10"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>新增 LLM 渠道</span>
          </button>
        ) : (
          <button
            onClick={openAddProfile}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-[14px] font-semibold rounded-lg shrink-0 cursor-pointer shadow-sm mb-2 h-10"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>新增总结模板</span>
          </button>
        )}
      </div>

      {activeTab === 'provider' ? (
        // LLM PROVIDER TAB TABLE
        <div className="space-y-4">
          <div className="overflow-x-auto bg-white rounded-xl border border-gray-100 shadow-[0_4px_20px_rgba(0,0,0,0.012)]">
            <table className="min-w-full divide-y divide-gray-100 text-[13px] text-gray-700">
              <thead className="bg-[#fcfdfe] text-gray-500 font-semibold text-xs select-none border-b border-gray-100">
                <tr>
                  <th className="px-6 py-4 text-left">配置ID</th>
                  <th className="px-6 py-4 text-left">名称</th>
                  <th className="px-6 py-4 text-left">状态</th>
                  <th className="px-6 py-4 text-left">接口类型</th>
                  <th className="px-6 py-4 text-center">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 bg-white">
                {providers.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-6 py-10 text-center text-gray-400 select-none">
                      暂无任何 LLM Provider 驱动配置
                    </td>
                  </tr>
                ) : (
                  providers.map((p) => (
                    <tr key={p.id} className="hover:bg-slate-50/45 transition-all">
                      <td className="px-6 py-4 font-mono text-xs text-gray-500 font-medium">{p.id}</td>
                      <td className="px-6 py-4 font-semibold text-gray-900">{p.name}</td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2.5">
                          <button
                            type="button"
                            onClick={() => handleToggleProviderEnabled(p)}
                            className={`relative inline-flex h-5 w-9 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none ${
                              p.enabled ? 'bg-indigo-600' : 'bg-gray-200'
                            }`}
                            title={p.enabled ? '点击禁用' : '点击启用'}
                          >
                            <span
                              className={`pointer-events-none inline-block h-4 w-4 transform rounded-full bg-white shadow-xs transition duration-200 ease-in-out ${
                                p.enabled ? 'translate-x-4' : 'translate-x-0'
                              }`}
                            />
                          </button>
                          <span className={`text-xs font-semibold select-none ${p.enabled ? 'text-indigo-600' : 'text-gray-400'}`}>
                            {p.enabled ? '启用' : '禁用'}
                          </span>
                        </div>
                      </td>
                      <td className="px-6 py-4">
                        <span className={`px-2.5 py-1 text-[10px] uppercase font-bold rounded-md border select-none ${
                          p.provider_type === 'openai'
                            ? 'bg-emerald-50 text-emerald-700 border-emerald-100/55'
                            : p.provider_type === 'anthropic'
                            ? 'bg-amber-50 text-amber-700 border-amber-100/55'
                            : 'bg-indigo-50 text-indigo-700 border-indigo-100/55'
                        }`}>
                          {p.provider_type === 'openai_compatible' ? 'Compat API' : p.provider_type}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <div className="flex items-center justify-center gap-2 text-xs">
                          <button
                            onClick={() => openEditProvider(p)}
                            className="px-2.5 py-1.5 font-semibold text-slate-700 bg-white border border-slate-200 hover:bg-slate-50 active:scale-95 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1 shrink-0"
                          >
                            <span>编辑</span>
                          </button>
                          <div className="h-4 w-px bg-gray-200" />
                          <button
                            onClick={() => handleDeleteProvider(p.id, p.name)}
                            className="px-2.5 py-1.5 font-semibold text-red-600 bg-red-50 hover:bg-red-500 hover:text-white border border-red-100 active:scale-95 rounded-lg cursor-pointer transition-all inline-flex items-center gap-1 shrink-0"
                          >
                            <span>删除</span>
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>
      ) : (
        // SUMMARY PROFILES TAB GRID
        <div className="space-y-4">
          {providers.length === 0 ? (
            <div className="bg-amber-50 border border-amber-200 text-amber-800 rounded-xl p-6 text-center select-none text-xs font-semibold space-y-2">
              <AlertCircle className="w-8 h-8 text-amber-600 mx-auto" />
              <p>检测到您尚未在平台添加过任何 LLM Provider 联通通道。</p>
              <p className="text-gray-400">请前往第一页 “LLM Provider” 新增至少一个 API 校验通道之后，再行创建 Profile 重写策略！</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {profiles.map((p) => {
                const matchedProv = providers.find(pr => pr.id === p.llm_provider_id);
                return (
                  <div
                    key={p.id}
                    className={`bg-white rounded-xl border p-5 shadow-sm flex flex-col justify-between relative overflow-hidden ${
                      p.enabled ? 'border-[#e4e6ec]' : 'border-gray-200 opacity-60'
                    }`}
                  >
                    {p.is_default && (
                      <div className="absolute top-0 right-0 bg-[#7C3AED] text-white font-bold text-[9px] px-2.5 py-0.5 rounded-bl-lg tracking-wider block uppercase">
                        DEFAULT 默认
                      </div>
                    )}
                    <div className="space-y-3">
                      <div>
                        <h4 className="text-[16px] font-semibold text-gray-900 leading-none truncate" title={p.name}>{p.name}</h4>
                        <span className="text-[11px] text-gray-500 block mt-1">驱动引擎: {matchedProv ? matchedProv.name : '未绑定'}</span>
                      </div>

                      <div className="space-y-2.5 p-3 rounded-lg bg-gray-50/50 border border-gray-100">
                        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono">
                          <div>
                            <span className="text-gray-400 block uppercase text-[8px]">运行模型</span>
                            <span className="text-gray-700 block font-bold truncate" title={p.model || '未绑定'}>{p.model || '未绑定'}</span>
                          </div>
                          <div>
                            <span className="text-gray-400 block uppercase text-[8px]">MAX OUTPUT TOKENS</span>
                            <span className="text-gray-700 block font-bold mt-0.5">{p.max_output_tokens}</span>
                          </div>
                        </div>

                        <div className="grid grid-cols-2 gap-2 text-[10px] font-mono border-t border-gray-100 pt-1.5">
                          <div>
                            <span className="text-gray-400 block uppercase text-[8px]">PROMPT VERSION</span>
                            <span className="text-gray-700 block font-bold mt-0.5">#{p.prompt_version}</span>
                          </div>
                          <div>
                            <span className="text-gray-400 block uppercase text-[8px]">TEMPERATURE</span>
                            <span className="text-gray-700 block font-bold mt-0.5">{p.temperature}</span>
                          </div>
                        </div>
                      </div>

                      <div className="space-y-1 text-xs">
                        <span className="text-gray-400 block font-bold uppercase text-[9px]">SYSTEM PROMPT PREVIEW</span>
                        <p className="text-gray-600 leading-relaxed font-mono bg-white p-2 border border-gray-100 rounded-md h-[72px] overflow-y-auto block whitespace-pre-wrap">
                          {p.system_prompt || '未绑定系统级 System Prompt 提示词.'}
                        </p>
                      </div>
                    </div>

                    <div className="pt-3 border-t border-gray-100 flex items-center justify-between text-xs mt-4">
                      <span className="text-[10px] text-gray-400">
                        策略: {p.enabled ? '已激活' : '停用'}
                      </span>
                      <div className="flex items-center gap-2 text-xs">
                        {!p.is_default && (
                          <>
                            <button
                              onClick={() => handleSetDefaultProfile(p.id, p.name)}
                              className="px-2 py-1 font-semibold text-indigo-600 hover:text-indigo-805 rounded-md cursor-pointer transition-all"
                            >
                              设为默认
                            </button>
                            <div className="h-3.5 w-px bg-gray-200" />
                          </>
                        )}
                        <button
                          onClick={() => openEditProfile(p)}
                          className="px-2 py-1 font-semibold text-slate-700 hover:text-slate-900 rounded-md cursor-pointer transition-all"
                        >
                          编辑
                        </button>
                        <div className="h-3.5 w-px bg-gray-200" />
                        <button
                          onClick={() => handleDeleteProfile(p.id, p.name)}
                          className="px-2 py-1 font-semibold text-red-600 hover:text-red-800 rounded-md cursor-pointer transition-all"
                        >
                          删除
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* LLM Provider Form Drawer */}
      {providerModal && (
        <div className="fixed inset-0 z-50 overflow-hidden" onClick={() => setProviderModal(false)}>
          <div className="absolute inset-0 bg-black/40 transition-opacity" />
          <div className="absolute inset-y-0 right-0 max-w-full flex pl-10">
            <div
              className="w-screen max-w-md bg-white shadow-2xl flex flex-col h-full transform transition-all duration-300"
              onClick={(e) => e.stopPropagation()}
            >
              <form onSubmit={handleSaveProvider} className="flex flex-col h-full bg-white">
                <div className="px-6 py-5 border-b border-gray-100 bg-slate-50/50 flex justify-between items-center shrink-0">
                  <div>
                    <h3 className="font-bold text-gray-900 text-sm">
                      {editingProviderId ? '编辑渠道' : '新增渠道'}
                    </h3>
                  </div>
                  <button type="button" onClick={() => setProviderModal(false)} className="text-gray-400 hover:text-gray-600 focus:outline-none cursor-pointer">
                    <X className="w-4 h-4" />
                  </button>
                </div>

                <div className="flex-1 overflow-y-auto p-6 space-y-5">
                  {/* Provider Name */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block">名称</label>
                    <input
                      type="text"
                      required
                      value={provName}
                      onChange={(e) => setProvName(e.target.value)}
                      placeholder="例如: DeepSeek 官方渠道"
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-medium"
                    />
                  </div>

                  {/* Enable Switch */}
                  <div className="flex items-center justify-between pt-2">
                    <div className="space-y-0.5">
                      <span className="text-xs font-semibold text-gray-800">是否启用</span>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={provEnabled}
                        onChange={(e) => setProvEnabled(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                    </label>
                  </div>

                  {/* Type select */}
                  <div className="space-y-1 z-30">
                    <label className="text-xs font-semibold text-gray-700 block">接口类型</label>
                    <CustomSelect
                      options={[
                        { value: "openai", label: "OpenAI" },
                        { value: "anthropic", label: "Anthropic" },
                        { value: "openai_compatible", label: "OpenAI-Compatible" },
                      ]}
                      value={provType}
                      onChange={(val) => setProvType(val as any)}
                    />
                  </div>

                  {/* Base url */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block">Base URL</label>
                    <input
                      type="text"
                      value={provBaseUrl}
                      onChange={(e) => setProvBaseUrl(e.target.value)}
                      placeholder="OpenAI 官方接口可留空，兼容接口必填"
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono"
                    />
                  </div>

                  {/* API Key */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block">API KEY</label>
                    <input
                      type="password"
                      value={provApiKey}
                      onChange={(e) => setProvApiKey(e.target.value)}
                      placeholder={editingProviderId ? '不修改请留空' : '输入渠道 API KEY'}
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono"
                    />
                  </div>

                  {/* Supports model list / tags list */}
                  <div className="space-y-2.5">
                    <div className="flex items-center justify-between">
                      <label className="text-xs font-semibold text-gray-700 block">模型列表</label>
                      <button
                        type="button"
                        onClick={handleTriggerFetchUpstream}
                        disabled={fetchingModels}
                        className="text-[10px] text-indigo-600 hover:text-indigo-700 font-semibold flex items-center gap-1 cursor-pointer disabled:opacity-50 select-none bg-indigo-50/80 px-2 py-1 rounded"
                      >
                        <RefreshCw className={`w-2.5 h-2.5 ${fetchingModels ? 'animate-spin' : ''}`} />
                        <span>{fetchingModels ? '同步中...' : '自动获取上游'}</span>
                      </button>
                    </div>

                    {/* Manual input tag add */}
                    <div className="flex gap-2">
                      <input
                        type="text"
                        value={newModelInput}
                        onChange={(e) => setNewModelInput(e.target.value)}
                        placeholder="手动填入模型ID，回车或确定添加"
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            handleAddManualModel();
                          }
                        }}
                        className="flex-1 px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono"
                      />
                      <button
                        type="button"
                        onClick={handleAddManualModel}
                        className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-lg text-xs font-semibold select-none cursor-pointer"
                      >
                        新增
                      </button>
                    </div>

                    {/* Model list tags */}
                    <div className="flex flex-wrap gap-1.5 p-3 rounded-lg border border-slate-100 bg-slate-50/35 max-h-[160px] overflow-y-auto">
                      {provSupportedModels.length === 0 ? (
                        <span className="text-xs text-gray-400 select-none">暂无可用模型，请手动输入或自动获取</span>
                      ) : (
                        provSupportedModels.map(m => (
                          <span
                            key={m}
                            className="inline-flex items-center gap-1 pl-2.5 pr-1.5 py-1 rounded-md text-xs font-mono font-semibold bg-white text-gray-700 border border-gray-200 select-none transition-all"
                          >
                            <span className="max-w-[200px] truncate" title={m}>
                              {m}
                            </span>
                            <button
                              type="button"
                              onClick={() => handleRemoveSupportedModel(m)}
                              className="w-4 h-4 hover:bg-red-50 text-gray-400 hover:text-red-600 rounded-full inline-flex items-center justify-center font-sans font-medium text-[10px] cursor-pointer"
                            >
                              &times;
                            </button>
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2 bg-slate-50/55 shrink-0">
                  <button
                    type="button"
                    onClick={() => setProviderModal(false)}
                    className="px-4 py-2 border border-gray-200 text-gray-500 rounded-lg text-xs font-semibold hover:bg-gray-50 cursor-pointer"
                  >
                    取消
                  </button>
                  <button
                    type="submit"
                    disabled={saving}
                    className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold inline-flex items-center gap-2 cursor-pointer shadow-sm"
                  >
                    {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                    <span>保存设置</span>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Upstream check Selection Popup Modal */}
      {upstreamFetchModal && (
        <div className="fixed inset-0 z-[60] overflow-y-auto" onClick={() => setUpstreamFetchModal(false)}>
          <div className="fixed inset-0 bg-black/50 transition-opacity" />
          <div className="flex items-center justify-center min-h-screen p-4">
            <div
              className="bg-white rounded-xl overflow-hidden border border-slate-200 shadow-2xl w-full max-w-sm transform transition-all z-10"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="px-5 py-4 border-b border-gray-100 bg-slate-50/60 flex justify-between items-center">
                <div>
                  <h4 className="font-bold text-gray-950 text-xs">选择需要加入的模型列表</h4>
                  <p className="text-[10px] text-gray-400 mt-0.5">勾选希望导入支持的模型规格</p>
                </div>
                <button type="button" onClick={() => setUpstreamFetchModal(false)} className="text-gray-400 hover:text-gray-600 font-bold text-sm">
                  &times;
                </button>
              </div>

              <div className="p-5 space-y-4 max-h-[300px] overflow-y-auto">
                {fetchedModelsList.length === 0 ? (
                  <p className="text-center text-xs text-gray-400 py-6">未检测到任何上游模型</p>
                ) : (
                  <div className="grid grid-cols-1 gap-2">
                    {fetchedModelsList.map(m => {
                      const checked = selectedUpstreamModels.includes(m);
                      return (
                        <label
                          key={m}
                          className={`flex items-center gap-3 p-2 rounded-lg border text-xs font-mono font-medium transition-all cursor-pointer ${
                            checked ? 'bg-indigo-50/45 border-indigo-200 text-indigo-950' : 'bg-white border-gray-100 text-gray-700'
                          }`}
                        >
                          <input
                            type="checkbox"
                            checked={checked}
                            onChange={(e) => {
                              if (e.target.checked) {
                                setSelectedUpstreamModels([...selectedUpstreamModels, m]);
                              } else {
                                setSelectedUpstreamModels(selectedUpstreamModels.filter(cur => cur !== m));
                              }
                            }}
                            className="rounded text-indigo-600 focus:ring-indigo-500 border-gray-300 w-4 h-4 cursor-pointer"
                          />
                          <span className="truncate" title={m}>{m}</span>
                        </label>
                      );
                    })}
                  </div>
                )}
              </div>

              <div className="px-5 py-3 border-t border-gray-100 bg-slate-50 flex justify-between items-center gap-2">
                <button
                  type="button"
                  onClick={() => {
                    if (selectedUpstreamModels.length === fetchedModelsList.length) {
                      setSelectedUpstreamModels([]);
                    } else {
                      setSelectedUpstreamModels(fetchedModelsList);
                    }
                  }}
                  className="px-2.5 py-1.5 border border-slate-200 text-gray-600 bg-white hover:bg-slate-50 rounded-lg text-[10px] font-bold"
                >
                  {selectedUpstreamModels.length === fetchedModelsList.length ? '取消全选' : '全选所有'}
                </button>
                <div className="flex gap-1">
                  <button
                    type="button"
                    onClick={() => setUpstreamFetchModal(false)}
                    className="px-3 py-1.5 border border-slate-200 text-gray-500 hover:bg-slate-50 rounded-lg text-[10px] font-bold"
                  >
                    取消
                  </button>
                  <button
                    type="button"
                    onClick={handleConfirmImportUpstream}
                    className="px-3.5 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-[10px] font-bold shadow-xs"
                  >
                    确定导入
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Summary Profile Modal */}
      {profileModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 p-4" onClick={() => setProfileModal(false)}>
          <div
            className="w-full max-w-xl bg-white rounded-xl border border-[#e4e6ec] shadow-xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <form onSubmit={handleSaveProfile}>
              <div className="px-6 py-4 border-b border-[#e4e6ec] bg-[#fbfbfe] flex justify-between items-center">
                <h3 className="font-bold text-gray-900 text-sm">
                  {editingProfileId ? '编辑' : '新增'} 摘要 Profile 模板
                </h3>
                <button type="button" onClick={() => setProfileModal(false)} className="text-gray-400 hover:text-gray-600 focus:outline-none">
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
                <div className="grid grid-cols-2 gap-4">
                  {/* Profile Name */}
                  <div className="space-y-1col-span-2">
                    <label className="text-xs font-semibold text-gray-700 block">Profile 别名 *</label>
                    <input
                      type="text"
                      required
                      value={profName}
                      onChange={(e) => setProfName(e.target.value)}
                      placeholder="例如: 财务讨论专属摘要格式"
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  {/* Provider id selection */}
                  <div className="space-y-1 z-20">
                    <label className="text-xs font-semibold text-gray-700 block">绑定驱动通道LLM Provider *</label>
                    <CustomSelect
                      options={providers.map(pr => ({
                        value: String(pr.id),
                        label: pr.name
                      }))}
                      value={profProviderId}
                      onChange={(val) => setProfProviderId(val)}
                      searchable={providers.length > 5}
                    />
                  </div>

                  {/* Override model name */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block flex items-center justify-between">
                      <span className="flex items-center gap-1">运行模型 <span className="text-red-500">*</span></span>
                      {loadingProfileModels && (
                        <span className="text-[10px] text-indigo-500 animate-pulse font-normal">同步最新模型中...</span>
                      )}
                    </label>

                    <div className="space-y-1 z-20">
                      <CustomSelect
                        options={((profileModels && profileModels.length > 0)
                          ? profileModels
                          : (providers.find(p => String(p.id) === profProviderId)
                              ? (TYPE_PRESETS[providers.find(p => String(p.id) === profProviderId)!.provider_type] || TYPE_PRESETS.openai_compatible)
                              : []
                            )
                        ).map((m) => ({ value: m, label: m }))}
                        value={profModel}
                        onChange={(val) => {
                          setProfModel(val);
                        }}
                      />
                    </div>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-4">
                  {/* Prompt version */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block">模板版本号</label>
                    <input
                      type="text"
                      required
                      value={profPromptVersion}
                      onChange={(e) => setProfPromptVersion(e.target.value || 'v1')}
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono"
                    />
                  </div>

                  {/* Temperature */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block">模型温度</label>
                    <input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      required
                      value={profTemp}
                      onChange={(e) => setProfTemp(parseFloat(e.target.value) || 0.5)}
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono"
                    />
                  </div>

                  {/* Output tokens limit */}
                  <div className="space-y-1">
                    <label className="text-xs font-semibold text-gray-700 block">最大输出 Token</label>
                    <input
                      type="number"
                      required
                      value={profTokens}
                      onChange={(e) => setProfTokens(parseInt(e.target.value) || 2048)}
                      className="w-full px-3 py-2 rounded-lg border border-[#e4e6ec] text-xs font-mono"
                    />
                  </div>
                </div>

                {/* System Prompt logic */}
                <div className="space-y-1">
                  <label className="text-xs font-semibold text-gray-700 block">System Prompt 系统提示词 *</label>
                  <textarea
                    required
                    rows={4}
                    value={profSystemPrompt}
                    onChange={(e) => setProfSystemPrompt(e.target.value)}
                    placeholder="输入大模型的 System Instruction。在此指导其排版、话题聚合及任务期望..."
                    className="w-full p-3 rounded-lg border border-[#e4e6ec] text-xs font-mono leading-relaxed"
                  />
                </div>

                {/* Enable and Default settings */}
                <div className="pt-2 divide-y divide-gray-100 space-y-3">
                  <div className="flex items-center justify-between pt-1">
                    <div className="space-y-0.5">
                      <span className="text-xs font-semibold text-gray-800">激活当前 Profile 模板</span>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={profEnabled}
                        onChange={(e) => setProfEnabled(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                    </label>
                  </div>

                  <div className="flex items-center justify-between pt-3">
                    <div className="space-y-0.5">
                      <span className="text-xs font-semibold text-gray-800">设为全局缺省默认摘要 Profile</span>
                    </div>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        checked={profDefault}
                        onChange={(e) => setProfDefault(e.target.checked)}
                        className="sr-only peer"
                      />
                      <div className="w-9 h-5 bg-gray-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-indigo-600"></div>
                    </label>
                  </div>
                </div>
              </div>

              <div className="px-6 py-4 border-t border-gray-100 flex justify-end gap-2 bg-[#fafafa]">
                <button
                  type="button"
                  onClick={() => setProfileModal(false)}
                  className="px-4 py-2 border border-gray-200 text-gray-500 rounded-lg text-xs font-semibold hover:bg-gray-50 cursor-pointer"
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={saving}
                  className="px-5 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold inline-flex items-center gap-2 cursor-pointer shadow-sm"
                >
                  {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                  <span>保存摘要模板</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Custom Delete Confirmation Modal */}
      {confirmModal && (
        <div
          className="fixed inset-0 bg-black/45 flex items-center justify-center z-50 p-4"
          onClick={() => setConfirmModal(null)}
        >
          <div
            className="bg-white rounded-xl border border-gray-100 max-w-sm w-full shadow-lg overflow-hidden animate-in fade-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="p-6 text-center space-y-4">
              <div className="w-12 h-12 rounded-full bg-red-50 text-red-600 flex items-center justify-center mx-auto">
                <AlertCircle className="w-6 h-6 animate-pulse" />
              </div>
              <div className="space-y-1">
                <h4 className="text-[16px] font-bold text-gray-900">安全删除校验</h4>
                <p className="text-xs text-gray-500 leading-relaxed font-sans">
                  您确定要删除{confirmModal.type === 'provider' ? ' LLM 驱动通道' : '提示词模板'} <strong className="text-red-600">"{confirmModal.name}"</strong> 吗？
                  <span className="block mt-1 font-medium text-red-500">此动作将立刻删除且无法撤消！</span>
                </p>
              </div>
            </div>
            <div className="px-6 py-4 bg-[#fbfbfe] border-t border-gray-100 flex items-center justify-end gap-2">
              <button
                type="button"
                onClick={() => setConfirmModal(null)}
                className="px-4 py-2 border border-gray-200 text-gray-500 rounded-lg text-xs font-semibold hover:bg-gray-50 cursor-pointer transition-all"
              >
                取消
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                disabled={saving}
                className="px-5 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-xs font-semibold inline-flex items-center gap-1.5 cursor-pointer shadow-sm transition-all"
              >
                {saving && <RefreshCw className="w-3.5 h-3.5 animate-spin" />}
                <span>确认删除</span>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
