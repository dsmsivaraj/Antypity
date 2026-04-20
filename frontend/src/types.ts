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
