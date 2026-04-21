export type AgentSummary = {
  name: string
  description: string
  capabilities: string[]
  supports_tools: boolean
  preferred_model?: string | null
}

export type ModelSummary = {
  id: string
  provider: string
  mode: string
  description: string
  deployment?: string | null
}

export type ModelListResponse = {
  models: ModelSummary[]
}

export type ExecutionResponse = {
  execution_id: string
  agent_name: string
  status: string
  output: string
  used_llm: boolean
  model_profile?: string | null
  provider?: string | null
  created_at: string
  context: Record<string, unknown>
}

export type ExecutionHistoryResponse = {
  executions: ExecutionResponse[]
}

export type HealthResponse = {
  status: string
  service: string
  version: string
  llm_enabled: boolean
  storage_backend: string
  auth_enabled: boolean
  auth_bootstrap_required: boolean
  timestamp: string
}

export type AuthStatusResponse = {
  auth_enabled: boolean
  bootstrap_required: boolean
}

export type ApiKeyCreateResponse = {
  id: string
  name: string
  role: string
  created_at: string
  is_active: boolean
  key: string
}

export type TaskPayload = {
  task: string
  agent_name?: string
  model_profile?: string
  context?: Record<string, unknown>
}

export interface SelfHealingAction {
  type: string
  service?: string
  file?: string
  result: string
}

export interface SelfHealingCycle {
  timestamp: string
  status: string
  initial_issues_count?: number
  final_issues_count?: number
  actions: SelfHealingAction[]
  error?: string
}

export interface SelfHealingStatus {
  is_running: boolean
  interval_seconds: number
  history: SelfHealingCycle[]
  last_cycle?: SelfHealingCycle
}

export interface User {
  id: string
  email: string
  full_name?: string
  role: string
  status: string
}

export interface Session {
  access_token: string
  user: User
}

export interface ResumeParseResponse {
  filename: string
  text: string
  metadata: Record<string, unknown>
}

export interface ResumeAnalysis {
  id?: string
  title: string
  source_filename?: string | null
  summary: string
  match_score: number
  suggestions: string[]
  ats_keywords: string[]
  strengths: string[]
  gaps: string[]
  recommended_roles: string[]
  model_profile?: string | null
  used_llm: boolean
  provider?: string | null
  created_at?: string | null
}

export interface ResumeChatResponse {
  answer: string
  used_llm: boolean
  provider: string
  model_profile: string
  suggested_questions: string[]
}

export interface ResumeTemplate {
  id: string
  name: string
  target_role: string
  style: string
  figma_prompt: string
  sections: string[]
  design_tokens: Record<string, string>
  preview_markdown: string
  source: string
  model_profile?: string | null
  created_at?: string | null
}

export interface ResumeTemplateListResponse {
  templates: ResumeTemplate[]
}

export interface JobSource {
  id: string
  label: string
  hosts: string[]
  search_url: string
}

export interface JobSourceListResponse {
  sources: JobSource[]
}

export interface JobDescriptionResponse {
  title: string
  company: string
  description: string
  source: string
  source_type: string
  keywords: string[]
}

export interface JobSearchResult {
  id: string
  title: string
  company: string
  location: string
  url: string
  source: string
  summary: string
  ats_score?: number | null
}

export interface CareerAnalytics {
  total_resume_analyses: number
  total_templates: number
  total_job_queries: number
  total_job_results: number
  average_match_score: number
  top_sources: Record<string, number>
}

export type DiagnosticIssue = {
  severity: 'critical' | 'warning' | 'info'
  category: string
  message: string
  file?: string | null
  line?: number | null
  suggestion?: string | null
}

export type DiagnosticTestResult = {
  passed: number
  failed: number
  errors: number
  duration_seconds: number
  status: string
  output: string
}

export type DiagnosticRunResponse = {
  id: string
  status: 'healthy' | 'degraded' | 'failing'
  health?: Record<string, string> | null
  tests?: DiagnosticTestResult | null
  issues: DiagnosticIssue[]
  summary: string
  created_at: string
  completed_at?: string | null
}

export type DiagnosticRunListResponse = {
  runs: DiagnosticRunResponse[]
}

export type ChatMessage = {
  role: string
  content: string
  timestamp?: string | null
}

export type ChatHistoryResponse = {
  session_id: string
  messages: ChatMessage[]
}

// ── Resume Skills ────────────────────────────────────────────────────────────

export interface ResumeEvaluationResponse {
  overall_score: number
  grade: string
  ats_risk_level: string
  summary: string
  dimensions: Record<string, { score: number; max: number; notes: string }>
  top_strengths: string[]
  critical_fixes: string[]
  missing_sections: string[]
  used_llm: boolean
  provider?: string | null
}

export interface ResumeWrittenContent {
  professional_summary: string
  experience_bullets: string[]
  skills_section: { technical?: string[]; tools?: string[]; soft_skills?: string[] }
  objective_statement: string
  keywords_embedded: string[]
  writing_notes: string
}

export interface ResumeWriteResponse {
  target_role: string
  written_content: ResumeWrittenContent
  used_llm: boolean
  provider?: string | null
}

export interface ResumeSectionFeedback {
  score: number
  feedback: string
  fixes: string[]
}

export interface ResumeReviewResponse {
  overall_verdict: string
  interview_probability: string
  sections: Record<string, ResumeSectionFeedback>
  top_3_immediate_actions: string[]
  red_flags: string[]
  interview_tips: string[]
  used_llm: boolean
  provider?: string | null
}

// ── Job Hunt ──────────────────────────────────────────────────────────────────

export interface JobOpportunity {
  id: string
  company: string
  role: string
  sector: string
  company_type: string
  location: string
  apply_url: string
  career_url: string
  fit_score: number
  package_lpa: string
  tier: 'high' | 'medium' | 'stretch'
}

export interface TailoredApplication {
  company: string
  role: string
  apply_url: string
  fit_score: number
  tailored_content: {
    tailored_summary?: string
    rewritten_bullets?: string[]
    skills_to_highlight?: string[]
    skills_to_add?: string[]
    cover_line?: string
  }
}

export interface LiveJobResult {
  id: string
  title: string
  company: string
  location: string
  url: string
  source: string
  source_label: string
  result_type: 'listing' | 'portal_search'
  jd_snippet: string
  jd_full: string
  published?: string
  tier: 'high' | 'medium' | 'stretch'
  match_score: number
  matched_keywords: string[]
  missing_keywords: string[]
  improvement_areas: string[]
  ats_summary: string
}

export interface LiveJobHuntResponse {
  candidate_name: string
  target_roles: string[]
  total_found: number
  jobs: LiveJobResult[]
  high_tier: LiveJobResult[]
  medium_tier: LiveJobResult[]
  stretch_tier: LiveJobResult[]
}

export interface JobHuntResponse {
  candidate_name: string
  target_roles: string[]
  total_opportunities: number
  opportunities: JobOpportunity[]
  high_tier: JobOpportunity[]
  medium_tier: JobOpportunity[]
  stretch_tier: JobOpportunity[]
  tailored_applications: TailoredApplication[]
  profile: Record<string, unknown>
}
