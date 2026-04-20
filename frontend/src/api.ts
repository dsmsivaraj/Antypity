import type {
  AgentSummary,
  ApiKeyCreateResponse,
  AuthStatusResponse,
  DiagnosticRunListResponse,
  DiagnosticRunResponse,
  ExecutionHistoryResponse,
  ExecutionResponse,
  HealthResponse,
  ModelListResponse,
  SelfHealingStatus,
  TaskPayload,
  User,
  Session,
  ResumeAnalysis,
  JobSearchResult,
  Analytics,
} from './types'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:9500'
).replace(/\/$/, '')

const API_KEY_STORAGE_KEY = 'actypity_api_key'

export function getStoredApiKey(): string {
  if (typeof window === 'undefined') {
    return ''
  }
  return window.localStorage.getItem(API_KEY_STORAGE_KEY) || ''
}

export function setStoredApiKey(value: string): void {
  if (typeof window === 'undefined') {
    return
  }
  if (value.trim()) {
    window.localStorage.setItem(API_KEY_STORAGE_KEY, value.trim())
  } else {
    window.localStorage.removeItem(API_KEY_STORAGE_KEY)
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const apiKey = getStoredApiKey()
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(apiKey ? { 'X-API-Key': apiKey } : {}),
      ...(init?.headers ?? {}),
    },
    ...init,
  })

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        detail = payload.detail
      }
    } catch {
      // Keep the generic message when the response body is not JSON.
    }
    throw new Error(detail)
  }

  return (await response.json()) as T
}

export const api = {
  baseUrl: API_BASE_URL,
  getHealth: () => request<HealthResponse>('/health'),
  getAuthStatus: () => request<AuthStatusResponse>('/auth/status'),
  getAgents: () => request<AgentSummary[]>('/agents'),
  getModels: () => request<ModelListResponse>('/models'),
  getExecutions: () => request<ExecutionHistoryResponse>('/executions?limit=10'),
  executeTask: (payload: TaskPayload) =>
    request<ExecutionResponse>('/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getSelfHealingStatus: () => request<SelfHealingStatus>('/self-healing/status'),
  runDiagnostics: () =>
    request<DiagnosticRunResponse>('/diagnostics/run', { method: 'POST' }),
  getDiagnosticReports: (limit = 10) =>
    request<DiagnosticRunListResponse>(`/diagnostics/reports?limit=${limit}`),
  getLatestDiagnosticReport: () =>
    request<DiagnosticRunResponse>('/diagnostics/reports/latest'),

  // Identity
  loginSocial: (provider: string, token: string, email: string, name: string, socialId: string) =>
    request<Session>('/auth/social', {
      method: 'POST',
      body: JSON.stringify({ provider, token, email, full_name: name, social_id: socialId }),
    }),
  getMe: (token: string) => request<User>(`/users/me?token=${token}`),

  // ATS
  parseResume: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return fetch(`${API_BASE_URL}/resume/parse`, {
      method: 'POST',
      body: formData,
    }).then(res => res.json())
  },
  analyzeResume: (text: string, jdText: string) =>
    request<ResumeAnalysis>('/resume/analyze', {
      method: 'POST',
      body: JSON.stringify({ text, jd_text: jdText }),
    }),
  searchJobs: (keywords: string[]) =>
    request<JobSearchResult[]>('/job/search', {
      method: 'POST',
      body: JSON.stringify({ keywords }),
    }),
  getAnalytics: () => request<Analytics>('/tracker/analytics'),

  bootstrapAdminKey: (bootstrapToken: string, name: string) =>
    request<ApiKeyCreateResponse>('/auth/bootstrap', {
      method: 'POST',
      headers: {
        'X-Bootstrap-Token': bootstrapToken,
      },
      body: JSON.stringify({ name }),
    }),
}
