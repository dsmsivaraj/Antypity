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
  type: string;
  service?: string;
  file?: string;
  result: string;
}

export interface SelfHealingCycle {
  timestamp: string;
  status: string;
  initial_issues_count?: number;
  final_issues_count?: number;
  actions: SelfHealingAction[];
  error?: string;
}

export interface SelfHealingStatus {
  is_running: boolean;
  interval_seconds: number;
  history: SelfHealingCycle[];
  last_cycle?: SelfHealingCycle;
}

export interface User {
  id: string;
  email: string;
  full_name?: string;
  role: string;
  status: string;
}

export interface Session {
  access_token: string;
  user: User;
}

export interface ResumeAnalysis {
  text: string;
  suggestions: string[];
  ats_keywords: string[];
}

export interface JobSearchResult {
  id: string;
  title: string;
  company: string;
  location: string;
  url: string;
  ats_score?: number;
}

export interface Application {
  id: string;
  title: string;
  company: string;
  status: string;
  created_at: string;
}

export interface Analytics {
  total_applications: number;
  by_status: Record<string, number>;
  by_company: Record<string, number>;
  match_accuracy_avg: number;
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
