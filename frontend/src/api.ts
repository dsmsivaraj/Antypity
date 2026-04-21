import type {
  AgentSummary,
  ApiKeyCreateResponse,
  AuthStatusResponse,
  CareerAnalytics,
  ChatHistoryResponse,
  DiagnosticRunListResponse,
  DiagnosticRunResponse,
  ExecutionHistoryResponse,
  ExecutionResponse,
  HealthResponse,
  JobDescriptionResponse,
  JobHuntResponse,
  JobSearchResult,
  JobSourceListResponse,
  LiveJobHuntResponse,
  ModelListResponse,
  ResumeAnalysis,
  ResumeChatResponse,
  ResumeEvaluationResponse,
  ResumeParseResponse,
  ResumeReviewResponse,
  ResumeTemplate,
  ResumeTemplateListResponse,
  ResumeWriteResponse,
  SelfHealingStatus,
  Session,
  TaskPayload,
} from './types'

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:9500'
).replace(/\/$/, '')

const API_KEY_STORAGE_KEY = 'actypity_api_key'

export function getStoredApiKey(): string {
  if (typeof window === 'undefined') {
    return import.meta.env.VITE_API_KEY || ''
  }
  return window.localStorage.getItem(API_KEY_STORAGE_KEY) || import.meta.env.VITE_API_KEY || ''
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
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && !(init?.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }
  if (apiKey) {
    headers.set('X-API-Key', apiKey)
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers,
  })

  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`
    try {
      const payload = (await response.json()) as { detail?: string }
      if (payload.detail) {
        detail = payload.detail
      }
    } catch {
      // Keep generic message when the response is not JSON.
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

  loginSocial: (provider: string, token: string, email: string, name: string, socialId: string) =>
    request<Session>('/auth/social', {
      method: 'POST',
      body: JSON.stringify({ provider, token, email, full_name: name, social_id: socialId }),
    }),
  getMe: (token: string) => request<Session['user']>(`/users/me?token=${encodeURIComponent(token)}`),

  parseResume: async (file: File): Promise<ResumeParseResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    return request<ResumeParseResponse>('/resume/parse', {
      method: 'POST',
      body: formData,
    })
  },
  analyzeResume: (text: string, jdText: string, sourceFilename?: string, modelProfile?: string) =>
    request<ResumeAnalysis>('/resume/analyze', {
      method: 'POST',
      body: JSON.stringify({
        text,
        jd_text: jdText,
        source_filename: sourceFilename,
        model_profile: modelProfile,
      }),
    }),
  askResume: (question: string, resumeText: string, jdText: string, modelProfile?: string) =>
    request<ResumeChatResponse>('/resume/chat', {
      method: 'POST',
      body: JSON.stringify({
        question,
        resume_text: resumeText,
        jd_text: jdText,
        model_profile: modelProfile,
      }),
    }),
  getResumeTemplates: () =>
    request<ResumeTemplateListResponse>('/resume/templates'),
  designResumeTemplate: (payload: {
    name: string
    target_role: string
    style: string
    notes: string
    model_profile?: string
  }) =>
    request<ResumeTemplate>('/resume/templates/design', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getJobSources: () => request<JobSourceListResponse>('/job/sources'),
  extractJobDescription: (payload: { url?: string; text?: string }) =>
    request<JobDescriptionResponse>('/job/extract', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  searchJobs: (payload: { keywords: string[]; locations: string[]; sources: string[] }) =>
    request<JobSearchResult[]>('/job/search', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  evaluateResume: (text: string, jdText: string, modelProfile?: string) =>
    request<ResumeEvaluationResponse>('/resume/evaluate', {
      method: 'POST',
      body: JSON.stringify({ text, jd_text: jdText, model_profile: modelProfile }),
    }),
  writeResume: (payload: {
    resume_text?: string
    jd_text?: string
    target_role: string
    section?: string
    candidate_name?: string
    model_profile?: string
  }) =>
    request<ResumeWriteResponse>('/resume/write', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  reviewResume: (text: string, jdText: string, targetRole: string, modelProfile?: string) =>
    request<ResumeReviewResponse>('/resume/review', {
      method: 'POST',
      body: JSON.stringify({ text, jd_text: jdText, target_role: targetRole, model_profile: modelProfile }),
    }),
  huntJobs: (payload: {
    resume_text: string
    location?: string
    experience_years?: number
    top_count?: number
    model_profile?: string
  }) =>
    request<JobHuntResponse>('/jobs/hunt', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  liveHuntJobs: (payload: { resume_text: string; location?: string; experience_years?: number; model_profile?: string }) =>
    request<LiveJobHuntResponse>('/jobs/live-hunt', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getAnalytics: () => request<CareerAnalytics>('/tracker/analytics'),
  chat: (payload: { message: string; session_id: string; resume_text?: string; jd_text?: string }) =>
    request<{ session_id: string; response: string; provider: string; used_llm: boolean; turn: number }>('/chat', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getChatHistory: (sessionId: string) =>
    request<ChatHistoryResponse>(`/chat/history/${encodeURIComponent(sessionId)}`),
  clearChatSession: (sessionId: string) =>
    request<{ cleared: boolean; session_id: string }>(`/chat/session/${encodeURIComponent(sessionId)}`, {
      method: 'DELETE',
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
