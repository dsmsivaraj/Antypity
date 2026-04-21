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
  PlatformInsights,
  RecruiterContactResponse,
  ResumeAnalysis,
  ResumeChatResponse,
  CoverLetterResponse,
  ResumeEvaluationResponse,
  ResumeParseResponse,
  ResumeReviewResponse,
  ResumeTemplate,
  ResumeTemplateListResponse,
  ResumeWriteResponse,
  SelfHealingStatus,
  Session,
  TaskPayload,
  User,
  UserProfile,
} from './types'

const JWT_KEY = 'actypity_jwt'

export function getStoredJwt(): string {
  if (typeof window === 'undefined') return ''
  return window.localStorage.getItem(JWT_KEY) || ''
}

export function setStoredJwt(token: string): void {
  if (typeof window === 'undefined') return
  if (token) {
    window.localStorage.setItem(JWT_KEY, token)
  } else {
    window.localStorage.removeItem(JWT_KEY)
  }
}

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
  googleAuth: (idToken: string) =>
    request<{ access_token: string; token_type: string; user: User }>('/auth/google', {
      method: 'POST',
      body: JSON.stringify({ id_token: idToken }),
    }),
  getAuthMe: (jwt: string) =>
    fetch(`${API_BASE_URL}/auth/me`, {
      headers: { Authorization: `Bearer ${jwt}` },
    }).then(async (r) => {
      if (!r.ok) throw new Error(`Auth check failed: ${r.status}`)
      return r.json() as Promise<User>
    }),
  getMyProfile: (jwt: string) =>
    fetch(`${API_BASE_URL}/users/me/profile`, {
      headers: { Authorization: `Bearer ${jwt}` },
    }).then(async (r) => {
      if (!r.ok) throw new Error(`Profile fetch failed: ${r.status}`)
      return r.json() as Promise<UserProfile>
    }),
  updateMyProfile: (jwt: string, body: Record<string, unknown>) =>
    fetch(`${API_BASE_URL}/users/me/profile`, {
      method: 'PATCH',
      headers: { Authorization: `Bearer ${jwt}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(async (r) => {
      if (!r.ok) throw new Error(`Profile update failed: ${r.status}`)
      return r.json() as Promise<UserProfile>
    }),
  parseResumeAuthenticated: async (file: File, jwt: string): Promise<ResumeParseResponse> => {
    const formData = new FormData()
    formData.append('file', file)
    const apiKey = getStoredApiKey()
    const headers = new Headers()
    if (apiKey) headers.set('X-API-Key', apiKey)
    if (jwt) headers.set('Authorization', `Bearer ${jwt}`)
    const response = await fetch(`${API_BASE_URL}/resume/parse`, {
      method: 'POST',
      headers,
      body: formData,
    })
    if (!response.ok) {
      const payload = await response.json().catch(() => ({})) as { detail?: string }
      throw new Error(payload.detail || `Parse failed: ${response.status}`)
    }
    return response.json() as Promise<ResumeParseResponse>
  },

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
  createCoverLetter: (payload: {
    resume_text: string
    jd_text?: string
    target_role: string
    company_name: string
    hiring_manager_name?: string
    tone?: string
    model_profile?: string
  }) =>
    request<CoverLetterResponse>('/resume/cover-letter', {
      method: 'POST',
      body: JSON.stringify(payload),
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
  discoverRecruiterContacts: (payload: {
    company_name: string
    company_domain?: string
    job_url?: string
    source_text?: string
    target_role?: string
  }) =>
    request<RecruiterContactResponse>('/job/recruiter-contacts', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  getAnalytics: () => request<CareerAnalytics>('/tracker/analytics'),
  getPlatformInsights: () => request<PlatformInsights>('/platform/insights'),
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
