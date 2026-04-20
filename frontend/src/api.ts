import type {
  AgentSummary,
  ApiKeyCreateResponse,
  AuthStatusResponse,
  ExecutionHistoryResponse,
  ExecutionResponse,
  HealthResponse,
  TaskPayload,
} from './types'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
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
  getExecutions: () => request<ExecutionHistoryResponse>('/executions?limit=10'),
  executeTask: (payload: TaskPayload) =>
    request<ExecutionResponse>('/execute', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  bootstrapAdminKey: (bootstrapToken: string, name: string) =>
    request<ApiKeyCreateResponse>('/auth/bootstrap', {
      method: 'POST',
      headers: {
        'X-Bootstrap-Token': bootstrapToken,
      },
      body: JSON.stringify({ name }),
    }),
}
