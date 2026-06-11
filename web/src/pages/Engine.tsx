import { useEffect, useMemo, useState } from "react";
import {
  Button,
  Card,
  Empty,
  Input,
  InputNumber,
  Modal,
  Select,
  Skeleton,
  Switch,
  Tabs,
  Tag,
  TextArea,
  Toast,
  Typography
} from "../ui/semi";
import { IconPlus, IconRefresh, IconSave, IconStar, IconTestScore } from "@douyinfe/semi-icons";
import { api } from "../api/client";
import type { LLMProvider, SummaryProfile } from "../api/types";
import { confirmAction } from "../components/ConfirmAction";
import { SecretInput } from "../components/SecretInput";
import { StatusBadge } from "../components/StatusBadge";
import { formatDateTime } from "../utils/format";

const { Title, Text } = Typography;

type ProviderFormState = {
  name: string;
  provider_type: string;
  base_url: string;
  default_model: string;
  api_key: string;
  timeout_seconds: number;
  max_retries: number;
  enabled: boolean;
};

type ProfileFormState = {
  name: string;
  llm_provider_id: number | null;
  model: string;
  prompt_version: string;
  system_prompt: string;
  temperature: number | null;
  max_output_tokens: number | null;
  enabled: boolean;
  is_default: boolean;
};

function providerForm(provider?: LLMProvider): ProviderFormState {
  return {
    name: provider?.name || "",
    provider_type: provider?.provider_type || "anthropic",
    base_url: provider?.base_url || "",
    default_model: provider?.default_model || "",
    api_key: "",
    timeout_seconds: provider?.timeout_seconds || 30,
    max_retries: provider?.max_retries || 2,
    enabled: provider?.enabled ?? true
  };
}

function profileForm(profile?: SummaryProfile, providerId?: number | null): ProfileFormState {
  return {
    name: profile?.name || "",
    llm_provider_id: profile?.llm_provider.id || providerId || null,
    model: profile?.model || "",
    prompt_version: profile?.prompt_version || "v1",
    system_prompt: profile?.system_prompt || "",
    temperature: profile?.temperature ?? null,
    max_output_tokens: profile?.max_output_tokens ?? null,
    enabled: profile?.enabled ?? true,
    is_default: profile?.is_default ?? false
  };
}

export function Engine() {
  const [providers, setProviders] = useState<LLMProvider[]>([]);
  const [profiles, setProfiles] = useState<SummaryProfile[]>([]);
  const [loading, setLoading] = useState(true);
  const [providerModal, setProviderModal] = useState<{ open: boolean; provider?: LLMProvider }>({ open: false });
  const [providerState, setProviderState] = useState<ProviderFormState>(providerForm());
  const [profileModal, setProfileModal] = useState<{ open: boolean; profile?: SummaryProfile }>({ open: false });
  const [profileState, setProfileState] = useState<ProfileFormState>(profileForm());
  const [saving, setSaving] = useState(false);
  const [testingId, setTestingId] = useState<number | null>(null);

  const providerOptions = useMemo(
    () => providers.map((item) => ({ label: item.name, value: item.id })),
    [providers]
  );

  async function load() {
    setLoading(true);
    try {
      const [providerResponse, profileResponse] = await Promise.all([
        api.providers.list(),
        api.profiles.list()
      ]);
      setProviders(providerResponse.items);
      setProfiles(profileResponse.items);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  function openProviderModal(provider?: LLMProvider) {
    setProviderModal({ open: true, provider });
    setProviderState(providerForm(provider));
  }

  function openProfileModal(profile?: SummaryProfile) {
    setProfileModal({ open: true, profile });
    setProfileState(profileForm(profile, providers[0]?.id || null));
  }

  async function saveProvider() {
    setSaving(true);
    try {
      if (providerModal.provider) {
        const payload: Partial<{
          name: string;
          provider_type: string;
          base_url: string | null;
          api_key: string;
          default_model: string;
          timeout_seconds: number;
          max_retries: number;
          enabled: boolean;
        }> = {
          name: providerState.name,
          provider_type: providerState.provider_type,
          base_url: providerState.base_url.trim() || null,
          default_model: providerState.default_model,
          timeout_seconds: providerState.timeout_seconds,
          max_retries: providerState.max_retries,
          enabled: providerState.enabled
        };
        if (providerState.api_key.trim()) {
          payload.api_key = providerState.api_key;
        }
        await api.providers.update(providerModal.provider.id, payload);
      } else {
        if (!providerState.api_key.trim()) {
          Toast.warning("新增 Provider 必须填写 API key");
          return;
        }
        await api.providers.create({
          name: providerState.name,
          provider_type: providerState.provider_type,
          base_url: providerState.base_url.trim() || null,
          api_key: providerState.api_key,
          default_model: providerState.default_model,
          timeout_seconds: providerState.timeout_seconds,
          max_retries: providerState.max_retries,
          enabled: providerState.enabled
        });
      }
      Toast.success("Provider 已保存");
      setProviderModal({ open: false });
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function saveProfile() {
    if (profileState.llm_provider_id === null) {
      Toast.warning("请选择 Provider");
      return;
    }
    setSaving(true);
    try {
      const payload = {
        name: profileState.name,
        llm_provider_id: profileState.llm_provider_id,
        model: profileState.model.trim() || null,
        prompt_version: profileState.prompt_version,
        system_prompt: profileState.system_prompt.trim() || null,
        temperature: profileState.temperature,
        max_output_tokens: profileState.max_output_tokens,
        enabled: profileState.enabled,
        is_default: profileState.is_default
      };
      if (profileModal.profile) {
        await api.profiles.update(profileModal.profile.id, payload);
      } else {
        await api.profiles.create(payload);
      }
      Toast.success("Profile 已保存");
      setProfileModal({ open: false });
      await load();
    } finally {
      setSaving(false);
    }
  }

  async function testProvider(provider: LLMProvider) {
    setTestingId(provider.id);
    try {
      await api.providers.test(provider.id);
      Toast.success("测试完成");
      await load();
    } finally {
      setTestingId(null);
    }
  }

  async function setDefault(profile: SummaryProfile) {
    const confirmed = await confirmAction({
      title: "设为默认 Profile?",
      content: "v1 同一时间只允许一个默认 Summary Profile。确认后会顶掉当前默认项。",
      okText: "设为默认"
    });
    if (!confirmed) {
      return;
    }
    await api.profiles.setDefault(profile.id);
    Toast.success("默认 Profile 已更新");
    await load();
  }

  if (loading && providers.length === 0 && profiles.length === 0) {
    return <Skeleton active placeholder={<Skeleton.Paragraph rows={8} />} />;
  }

  return (
    <div className="page">
      <div className="page-head-row">
        <div>
          <Title heading={2}>摘要引擎</Title>
          <Text type="tertiary">先配置 LLM Provider，再用 Summary Profile 定义摘要方案。</Text>
        </div>
        <Button icon={<IconRefresh />} onClick={load}>
          刷新
        </Button>
      </div>

      <Tabs type="line">
        <Tabs.TabPane tab="LLM Provider" itemKey="provider">
          <div className="entity-grid">
            {providers.map((provider) => (
              <Card
                key={provider.id}
                title={
                  <div className="card-title-row">
                    <span>{provider.name}</span>
                    <StatusBadge status={provider.status} />
                  </div>
                }
              >
                <div className="entity-fields">
                  <div>
                    <Text type="tertiary">类型</Text>
                    <Text>{provider.provider_type}</Text>
                  </div>
                  <div>
                    <Text type="tertiary">default model</Text>
                    <Text>{provider.default_model}</Text>
                  </div>
                  <div>
                    <Text type="tertiary">base url</Text>
                    <Text>{provider.base_url || "-"}</Text>
                  </div>
                  <div>
                    <Text type="tertiary">API key</Text>
                    <Tag color={provider.secret.configured ? "green" : "grey"}>
                      {provider.secret.configured ? "已配置" : "未配置"}
                    </Tag>
                  </div>
                  <div>
                    <Text type="tertiary">最近验证</Text>
                    <Text>{formatDateTime(provider.last_validated_at)}</Text>
                  </div>
                  <div>
                    <Text type="tertiary">enabled</Text>
                    <Text>{provider.enabled ? "已启用" : "已禁用"}</Text>
                  </div>
                </div>
                <div className="card-actions">
                  <Button
                    size="small"
                    icon={<IconTestScore />}
                    loading={testingId === provider.id}
                    onClick={() => testProvider(provider)}
                  >
                    测试
                  </Button>
                  <Button size="small" onClick={() => openProviderModal(provider)}>
                    编辑
                  </Button>
                </div>
              </Card>
            ))}
            <button type="button" className="add-card-button" onClick={() => openProviderModal()}>
              <IconPlus />
              新增 Provider
            </button>
          </div>
        </Tabs.TabPane>

        <Tabs.TabPane tab="Summary Profile" itemKey="profile">
          {providers.length === 0 ? (
            <Empty description="请先创建 LLM Provider" />
          ) : (
            <div className="entity-grid">
              {profiles.map((profile) => (
                <Card
                  key={profile.id}
                  title={
                    <div className="card-title-row">
                      <span>{profile.name}</span>
                      {profile.is_default && <Tag color="violet" prefixIcon={<IconStar />}>默认</Tag>}
                    </div>
                  }
                >
                  <div className="entity-fields">
                    <div>
                      <Text type="tertiary">Provider</Text>
                      <Text>
                        {profile.llm_provider.name} · {profile.llm_provider.provider_type}
                      </Text>
                    </div>
                    <div>
                      <Text type="tertiary">model</Text>
                      <Text>
                        {profile.effective_model}{" "}
                        {profile.uses_provider_default_model ? <Tag>provider 默认</Tag> : <Tag color="blue">覆盖</Tag>}
                      </Text>
                    </div>
                    <div>
                      <Text type="tertiary">prompt version</Text>
                      <Text>{profile.prompt_version}</Text>
                    </div>
                    <div>
                      <Text type="tertiary">temperature</Text>
                      <Text>{profile.temperature ?? "-"}</Text>
                    </div>
                    <div>
                      <Text type="tertiary">max output</Text>
                      <Text>{profile.max_output_tokens ?? "-"}</Text>
                    </div>
                    <div>
                      <Text type="tertiary">enabled</Text>
                      <Text>{profile.enabled ? "已启用" : "已禁用"}</Text>
                    </div>
                  </div>
                  <div className="card-actions">
                    <Button size="small" onClick={() => openProfileModal(profile)}>
                      编辑
                    </Button>
                    <Button
                      size="small"
                      disabled={profile.is_default}
                      icon={<IconStar />}
                      onClick={() => setDefault(profile)}
                    >
                      {profile.is_default ? "已是默认" : "设为默认"}
                    </Button>
                  </div>
                </Card>
              ))}
              <button type="button" className="add-card-button" onClick={() => openProfileModal()}>
                <IconPlus />
                新增 Profile
              </button>
            </div>
          )}
        </Tabs.TabPane>
      </Tabs>

      <Modal
        title={providerModal.provider ? "编辑 LLM Provider" : "新增 LLM Provider"}
        visible={providerModal.open}
        onCancel={() => setProviderModal({ open: false })}
        footer={
          <div className="modal-actions">
            <Button onClick={() => setProviderModal({ open: false })}>取消</Button>
            <Button theme="solid" type="primary" icon={<IconSave />} loading={saving} onClick={saveProvider}>
              保存
            </Button>
          </div>
        }
      >
        <div className="form-stack">
          <div className="field-block">
            <Text strong>名称</Text>
            <Input value={providerState.name} onChange={(value) => setProviderState({ ...providerState, name: value })} />
          </div>
          <div className="form-grid-2">
            <div className="field-block">
              <Text strong>provider 类型</Text>
              <Select
                value={providerState.provider_type}
                optionList={[
                  { label: "anthropic", value: "anthropic" },
                  { label: "openai", value: "openai" },
                  { label: "openai_compatible", value: "openai_compatible" }
                ]}
                onChange={(value) => setProviderState({ ...providerState, provider_type: String(value) })}
              />
            </div>
            <div className="field-block">
              <Text strong>default model</Text>
              <Input
                value={providerState.default_model}
                onChange={(value) => setProviderState({ ...providerState, default_model: value })}
              />
            </div>
          </div>
          <div className="field-block">
            <Text strong>base url</Text>
            <Input
              value={providerState.base_url}
              placeholder="可选"
              onChange={(value) => setProviderState({ ...providerState, base_url: value })}
            />
          </div>
          <SecretInput
            label="API key"
            value={providerState.api_key}
            secret={providerModal.provider?.secret || { configured: false, updated_at: null }}
            onChange={(value) => setProviderState({ ...providerState, api_key: value })}
          />
          <div className="form-grid-2">
            <div className="field-block">
              <Text strong>timeout seconds</Text>
              <InputNumber
                value={providerState.timeout_seconds}
                min={1}
                onChange={(value) =>
                  setProviderState({ ...providerState, timeout_seconds: typeof value === "number" ? value : 30 })
                }
              />
            </div>
            <div className="field-block">
              <Text strong>max retries</Text>
              <InputNumber
                value={providerState.max_retries}
                min={0}
                onChange={(value) =>
                  setProviderState({ ...providerState, max_retries: typeof value === "number" ? value : 0 })
                }
              />
            </div>
          </div>
          <div className="switch-row">
            <Switch checked={providerState.enabled} onChange={(checked) => setProviderState({ ...providerState, enabled: checked })} />
            <Text>启用此 Provider</Text>
          </div>
        </div>
      </Modal>

      <Modal
        title={profileModal.profile ? "编辑 Summary Profile" : "新增 Summary Profile"}
        visible={profileModal.open}
        onCancel={() => setProfileModal({ open: false })}
        footer={
          <div className="modal-actions">
            <Button onClick={() => setProfileModal({ open: false })}>取消</Button>
            <Button theme="solid" type="primary" icon={<IconSave />} loading={saving} onClick={saveProfile}>
              保存
            </Button>
          </div>
        }
      >
        <div className="form-stack">
          <div className="field-block">
            <Text strong>名称</Text>
            <Input value={profileState.name} onChange={(value) => setProfileState({ ...profileState, name: value })} />
          </div>
          <div className="form-grid-2">
            <div className="field-block">
              <Text strong>关联 Provider</Text>
              <Select
                value={profileState.llm_provider_id ?? undefined}
                optionList={providerOptions}
                onChange={(value) => setProfileState({ ...profileState, llm_provider_id: Number(value) })}
              />
            </div>
            <div className="field-block">
              <Text strong>model</Text>
              <Input
                placeholder="留空使用 provider 默认"
                value={profileState.model}
                onChange={(value) => setProfileState({ ...profileState, model: value })}
              />
            </div>
          </div>
          <div className="form-grid-2">
            <div className="field-block">
              <Text strong>prompt version</Text>
              <Input
                value={profileState.prompt_version}
                onChange={(value) => setProfileState({ ...profileState, prompt_version: value })}
              />
            </div>
            <div className="field-block">
              <Text strong>temperature</Text>
              <InputNumber
                value={profileState.temperature ?? undefined}
                min={0}
                max={2}
                step={0.1}
                onChange={(value) =>
                  setProfileState({ ...profileState, temperature: typeof value === "number" ? value : null })
                }
              />
            </div>
          </div>
          <div className="field-block">
            <Text strong>max output tokens</Text>
            <InputNumber
              value={profileState.max_output_tokens ?? undefined}
              min={1}
              onChange={(value) =>
                setProfileState({ ...profileState, max_output_tokens: typeof value === "number" ? value : null })
              }
            />
          </div>
          <div className="field-block">
            <Text strong>system prompt</Text>
            <TextArea
              rows={4}
              value={profileState.system_prompt}
              onChange={(value: string) => setProfileState({ ...profileState, system_prompt: value })}
            />
          </div>
          <div className="switch-row">
            <Switch checked={profileState.enabled} onChange={(checked) => setProfileState({ ...profileState, enabled: checked })} />
            <Text>启用此 Profile</Text>
          </div>
          <div className="switch-row">
            <Switch checked={profileState.is_default} onChange={(checked) => setProfileState({ ...profileState, is_default: checked })} />
            <Text>设为默认</Text>
          </div>
        </div>
      </Modal>
    </div>
  );
}
