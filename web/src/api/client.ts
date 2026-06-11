import { Toast } from "../ui/semi";
import type {
  AuditLogListResponse,
  BotListResponse,
  BotValidateResponse,
  DashboardResponse,
  GroupDetail,
  GroupListResponse,
  GroupSummarySettings,
  LLMProvider,
  LLMProviderListResponse,
  LLMProviderTestResponse,
  SummaryJob,
  SummaryProfile,
  SummaryProfileListResponse,
  TriggerSummaryJobResponse
} from "./types";

const TOKEN_KEY = "summary_relay_webui_token";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function getStoredToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function setStoredToken(token: string): void {
  sessionStorage.setItem(TOKEN_KEY, token);
}

export function clearStoredToken(): void {
  sessionStorage.removeItem(TOKEN_KEY);
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const payload = await response.json();
    const error = payload?.error;
    return new ApiError(
      response.status,
      String(error?.code || "request_failed"),
      String(error?.message || "请求失败"),
      error?.details
    );
  } catch {
    return new ApiError(response.status, "request_failed", "请求失败");
  }
}

async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  options: { suppressToast?: boolean; allowUnauthorized?: boolean } = {}
): Promise<T> {
  const token = getStoredToken();
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(path, { ...init, headers });
  if (response.status === 401) {
    clearStoredToken();
    if (!options.allowUnauthorized) {
      window.dispatchEvent(new CustomEvent("webui:unauthorized"));
    }
    throw new ApiError(401, "unauthorized", "认证失败");
  }
  if (!response.ok) {
    const error = await readError(response);
    if (!options.suppressToast) {
      Toast.error(error.message || "请求失败");
    }
    throw error;
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

function jsonBody(payload: unknown): RequestInit {
  return {
    method: "POST",
    body: JSON.stringify(payload)
  };
}

function buildQuery(params: Record<string, string | number | boolean | null | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export const api = {
  dashboard: () => apiRequest<DashboardResponse>("/api/dashboard"),

  bot: {
    list: () => apiRequest<BotListResponse>("/api/bot"),
    update: (payload: {
      id: number;
      name?: string;
      owner_id?: number;
      enabled?: boolean;
      bot_token?: string;
    }) =>
      apiRequest("/api/bot", {
        method: "PATCH",
        body: JSON.stringify(payload)
      }),
    validate: (payload: { id: number; bot_token?: string }) =>
      apiRequest<BotValidateResponse>("/api/bot/validate", jsonBody(payload))
  },

  providers: {
    list: () => apiRequest<LLMProviderListResponse>("/api/llm-providers"),
    create: (payload: {
      name: string;
      provider_type: string;
      base_url?: string | null;
      api_key: string;
      default_model: string;
      timeout_seconds: number;
      max_retries: number;
      enabled: boolean;
    }) => apiRequest<LLMProvider>("/api/llm-providers", jsonBody(payload)),
    update: (id: number, payload: Partial<{
      name: string;
      provider_type: string;
      base_url: string | null;
      api_key: string;
      default_model: string;
      timeout_seconds: number;
      max_retries: number;
      enabled: boolean;
    }>) =>
      apiRequest<LLMProvider>(`/api/llm-providers/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      }),
    test: (id: number) =>
      apiRequest<LLMProviderTestResponse>(`/api/llm-providers/${id}/test`, { method: "POST" })
  },

  profiles: {
    list: () => apiRequest<SummaryProfileListResponse>("/api/summary-profiles"),
    create: (payload: {
      name: string;
      llm_provider_id: number;
      model: string | null;
      prompt_version: string;
      system_prompt: string | null;
      temperature: number | null;
      max_output_tokens: number | null;
      enabled: boolean;
      is_default: boolean;
    }) => apiRequest<SummaryProfile>("/api/summary-profiles", jsonBody(payload)),
    update: (id: number, payload: Partial<{
      name: string;
      llm_provider_id: number;
      model: string | null;
      prompt_version: string;
      system_prompt: string | null;
      temperature: number | null;
      max_output_tokens: number | null;
      enabled: boolean;
      is_default: boolean;
    }>) =>
      apiRequest<SummaryProfile>(`/api/summary-profiles/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      }),
    setDefault: (id: number) =>
      apiRequest<SummaryProfile>(`/api/summary-profiles/${id}/set-default`, { method: "POST" })
  },

  groups: {
    list: (params: {
      q?: string;
      enabled?: boolean | null;
      profile_id?: number | null;
      status?: string | null;
      limit?: number;
      cursor?: string | null;
    } = {}) => apiRequest<GroupListResponse>(`/api/groups${buildQuery(params)}`),
    detail: (id: number) => apiRequest<GroupDetail>(`/api/groups/${id}`),
    updateSettings: (id: number, payload: GroupSummarySettings) =>
      apiRequest<GroupSummarySettings>(`/api/groups/${id}/summary-settings`, {
        method: "PATCH",
        body: JSON.stringify(payload)
      }),
    triggerSummary: (id: number) =>
      apiRequest<TriggerSummaryJobResponse>(`/api/groups/${id}/summary-jobs`, { method: "POST" }),
    pollJob: (pollUrl: string) => apiRequest<SummaryJob>(pollUrl)
  },

  auditLogs: {
    list: (params: {
      entity_type?: string;
      action?: string;
      from?: string;
      to?: string;
      limit?: number;
      cursor?: string | null;
    } = {}) => apiRequest<AuditLogListResponse>(`/api/audit-logs${buildQuery(params)}`)
  }
};
