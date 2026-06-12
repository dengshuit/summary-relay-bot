import {
  DashboardData,
  BotInstance,
  BotValidationResponse,
  LLMProvider,
  SummaryProfile,
  GroupItem,
  GroupDetail,
  AuditLog,
  GroupSummarySettings,
  HistoricalSummary,
  PrivateRelaysResponse,
  SummaryJob
} from './types';

const TOKEN_KEY = 'summary_relay_bot_admin_token';

export function getStoredToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string) {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken() {
  sessionStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return !!getStoredToken();
}

/**
 * Handle API response parsing, centralizing 401 redirect logic.
 */
async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearStoredToken();
    // Dispatch a custom event so the UI can redirect gracefully
    window.dispatchEvent(new CustomEvent('api-unauthorized'));
    throw new Error('认证失败');
  }

  const contentType = response.headers.get('content-type');
  let data: any;
  if (contentType && contentType.includes('application/json')) {
    data = await response.json();
  } else {
    data = await response.text();
  }

  if (!response.ok) {
    const errMsg = data?.error?.message || data?.detail || `HTTP Error ${response.status}`;
    throw new Error(errMsg);
  }

  return data as T;
}

/**
 * Make an authenticated or unauthenticated fetch to /api/*
 */
export async function apiRequest<T>(
  method: string,
  path: string,
  body?: any,
  signal?: AbortSignal
): Promise<T> {
  const token = getStoredToken();
  const headers: HeadersInit = {
    'Accept': 'application/json',
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (body) {
    headers['Content-Type'] = 'application/json';
  }

  const response = await fetch(path, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
    signal,
  });

  return handleResponse<T>(response);
}

export const api = {
  // Authentication
  async login(token: string): Promise<{ success: boolean; token: string }> {
    // In our spec, we validate the token directly by calling whoami or trying to retrieve bot info
    const headers = { 'Authorization': `Bearer ${token}` };
    const response = await fetch('/api/bot', { headers });
    if (response.status === 401) {
      throw new Error('认证失败');
    }
    if (!response.ok) {
      throw new Error('认证失败');
    }
    setStoredToken(token);
    return { success: true, token };
  },

  // Dashboard
  async getDashboard(): Promise<DashboardData> {
    return apiRequest<DashboardData>('GET', '/api/dashboard');
  },

  // Bot Instances
  async getBots(): Promise<{ active: number | null; items: BotInstance[] }> {
    return apiRequest<{ active: number | null; items: BotInstance[] }>('GET', '/api/bot');
  },

  async createBot(data: { name: string; owner_id: number | string; enabled: boolean; bot_token: string }): Promise<BotInstance> {
    return apiRequest<BotInstance>('POST', '/api/bot', { ...data, owner_id: Number(data.owner_id) });
  },

  async updateBot(data: { id: number | string; name?: string; owner_id?: number | string; enabled?: boolean; bot_token?: string }): Promise<BotInstance> {
    const payload = {
      ...data,
      id: Number(data.id),
      owner_id: data.owner_id === undefined ? undefined : Number(data.owner_id),
    };
    return apiRequest<BotInstance>('PATCH', '/api/bot', payload);
  },

  async validateBot(data: { id: number | string; bot_token?: string | null }): Promise<BotValidationResponse> {
    return apiRequest<BotValidationResponse>('POST', '/api/bot/validate', {
      ...data,
      id: Number(data.id),
    });
  },

  // LLM Providers
  async getProviders(): Promise<LLMProvider[]> {
    return apiRequest<LLMProvider[]>('GET', '/api/llm-providers');
  },

  async createProvider(data: Partial<LLMProvider> & { name: string; provider_type: string; default_model: string }): Promise<LLMProvider> {
    return apiRequest<LLMProvider>('POST', '/api/llm-providers', data);
  },

  async updateProvider(id: number | string, data: Partial<LLMProvider>): Promise<LLMProvider> {
    return apiRequest<LLMProvider>('PATCH', `/api/llm-providers/${id}`, data);
  },

  async deleteProvider(id: number | string): Promise<{ success: boolean }> {
    return apiRequest<{ success: boolean }>('DELETE', `/api/llm-providers/${id}`);
  },

  async testProvider(id: number | string): Promise<{ success: boolean; detail: string }> {
    return apiRequest<{ success: boolean; detail: string }>('POST', `/api/llm-providers/${id}/test`);
  },

  async fetchUpstreamModels(data: { provider_type: string; base_url?: string; api_key?: string }): Promise<{ success: boolean; source: string; detail: string; models: string[] }> {
    return apiRequest<{ success: boolean; source: string; detail: string; models: string[] }>('POST', '/api/llm-providers/fetch-models', data);
  },

  async getProviderModels(id: number | string): Promise<{ success: boolean; models: string[] }> {
    return apiRequest<{ success: boolean; models: string[] }>('GET', `/api/llm-providers/${id}/models`);
  },

  // Summary Profiles
  async getProfiles(): Promise<SummaryProfile[]> {
    return apiRequest<SummaryProfile[]>('GET', '/api/summary-profiles');
  },

  async createProfile(data: Partial<SummaryProfile> & { name: string; llm_provider_id: number | string }): Promise<SummaryProfile> {
    return apiRequest<SummaryProfile>('POST', '/api/summary-profiles', {
      ...data,
      llm_provider_id: Number(data.llm_provider_id),
    });
  },

  async updateProfile(id: number | string, data: Partial<SummaryProfile>): Promise<SummaryProfile> {
    return apiRequest<SummaryProfile>('PATCH', `/api/summary-profiles/${id}`, {
      ...data,
      llm_provider_id: data.llm_provider_id === undefined ? undefined : Number(data.llm_provider_id),
    });
  },

  async deleteProfile(id: number | string): Promise<{ success: boolean }> {
    return apiRequest<{ success: boolean }>('DELETE', `/api/summary-profiles/${id}`);
  },

  async setDefaultProfile(id: number | string): Promise<SummaryProfile> {
    return apiRequest<SummaryProfile>('POST', `/api/summary-profiles/${id}/set-default`);
  },

  // Groups
  async getGroups(params: {
    q?: string;
    enabled?: boolean | string;
    profile_id?: number | string;
    status?: string;
    limit?: number;
    cursor?: string;
  }): Promise<{ items: GroupItem[]; next_cursor: string | null }> {
    const query = new URLSearchParams();
    if (params.q) query.append('q', params.q);
    if (params.enabled !== undefined && params.enabled !== '') {
      query.append('enabled', String(params.enabled));
    }
    if (params.profile_id) query.append('profile_id', String(params.profile_id));
    if (params.status) query.append('status', params.status);
    if (params.limit) query.append('limit', String(params.limit));
    if (params.cursor) query.append('cursor', params.cursor);

    return apiRequest<{ items: GroupItem[]; next_cursor: string | null }>(
      'GET',
      `/api/groups?${query.toString()}`
    );
  },

  async getGroupDetail(id: number | string): Promise<GroupDetail> {
    return apiRequest<GroupDetail>('GET', `/api/groups/${id}`);
  },

  async updateGroupSettings(id: number | string, settings: GroupSummarySettings): Promise<GroupDetail> {
    return apiRequest<GroupDetail>('PATCH', `/api/groups/${id}/summary-settings`, settings);
  },

  async triggerGroupSummary(id: number | string): Promise<{ job: SummaryJob; poll_url: string }> {
    return apiRequest<{ job: SummaryJob; poll_url: string }>('POST', `/api/groups/${id}/summary-jobs`);
  },

  // Poll job status via custom poll_url or standardized route
  async pollJob(pollUrl: string): Promise<SummaryJob> {
    return apiRequest<SummaryJob>('GET', pollUrl);
  },

  // Historical summaries list
  async getSummaries(params: {
    q?: string;
    status?: string;
    group_id?: number | string;
    from?: string;
    to?: string;
    limit?: number;
    cursor?: string;
  } = {}): Promise<{ items: HistoricalSummary[]; next_cursor: string | null }> {
    const query = new URLSearchParams();
    if (params.q) query.append('q', params.q);
    if (params.status) query.append('status', params.status);
    if (params.group_id) query.append('group_id', String(params.group_id));
    if (params.from) query.append('from', params.from);
    if (params.to) query.append('to', params.to);
    if (params.limit) query.append('limit', String(params.limit));
    if (params.cursor) query.append('cursor', params.cursor);
    const suffix = query.toString() ? `?${query.toString()}` : '';
    return apiRequest<{ items: HistoricalSummary[]; next_cursor: string | null }>(
      'GET',
      `/api/summaries${suffix}`
    );
  },

  async reloadBotRuntime(): Promise<{ accepted: boolean; status: string; detail: string }> {
    return apiRequest<{ accepted: boolean; status: string; detail: string }>('POST', '/api/system/reload-bot-runtime');
  },

  // Audit Logs
  async getAuditLogs(params: {
    entity_type?: string;
    action?: string;
    from?: string;
    to?: string;
    limit?: number;
    cursor?: string;
  }): Promise<{ items: AuditLog[]; next_cursor: string | null }> {
    const query = new URLSearchParams();
    if (params.entity_type) query.append('entity_type', params.entity_type);
    if (params.action) query.append('action', params.action);
    if (params.from) query.append('from', params.from);
    if (params.to) query.append('to', params.to);
    if (params.limit) query.append('limit', String(params.limit));
    if (params.cursor) query.append('cursor', params.cursor);

    return apiRequest<{ items: AuditLog[]; next_cursor: string | null }>(
      'GET',
      `/api/audit-logs?${query.toString()}`
    );
  },

  // Private Messaging Relays
  async getPrivateRelays(params: {
    direction?: string;
    status?: string;
    q?: string;
    limit?: number;
    cursor?: string;
  }): Promise<PrivateRelaysResponse> {
    const query = new URLSearchParams();
    if (params.direction) query.append('direction', params.direction);
    if (params.status) query.append('status', params.status);
    if (params.q) query.append('q', params.q);
    if (params.limit) query.append('limit', String(params.limit));
    if (params.cursor) query.append('cursor', params.cursor);

    return apiRequest<PrivateRelaysResponse>('GET', `/api/private-relays?${query.toString()}`);
  }
};
