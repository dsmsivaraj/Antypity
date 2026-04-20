from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiSchema(BaseModel):
    model_config = ConfigDict(protected_namespaces=())


# ── Health / Ready ──────────────────────────────────────────────────────────

class HealthResponse(ApiSchema):
    status: str
    service: str
    version: str
    llm_enabled: bool
    storage_backend: str
    auth_enabled: bool
    auth_bootstrap_required: bool
    timestamp: datetime


class ReadyResponse(ApiSchema):
    status: str
    checks: Dict[str, str]


# ── Agents ──────────────────────────────────────────────────────────────────

class AgentSummary(ApiSchema):
    name: str
    description: str
    capabilities: List[str]
    supports_tools: bool = False
    preferred_model: Optional[str] = None


class AgentScoreRequest(ApiSchema):
    task: str
    context: Dict[str, Any] = Field(default_factory=dict)


class AgentScoreResponse(ApiSchema):
    agent_name: str
    score: int


class AgentExecutionRequest(ApiSchema):
    task: str
    context: Dict[str, Any] = Field(default_factory=dict)
    model_profile: Optional[str] = None


class AgentExecutionResponse(ApiSchema):
    agent_name: str
    output: str
    used_llm: bool
    provider: str
    model_profile: Optional[str] = None


class ModelSummary(ApiSchema):
    id: str
    provider: str
    mode: str
    description: str
    deployment: Optional[str] = None


class ModelListResponse(ApiSchema):
    models: List[ModelSummary]


class ModelCompletionRequest(ApiSchema):
    prompt: str
    system_prompt: Optional[str] = None
    model_profile: Optional[str] = None


class ModelCompletionResponse(ApiSchema):
    content: str
    used_llm: bool
    provider: str
    model_profile: str


# ── Executions ──────────────────────────────────────────────────────────────

class TaskRequest(ApiSchema):
    task: str = Field(min_length=3, max_length=4000)
    agent_name: Optional[str] = None
    model_profile: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(ApiSchema):
    execution_id: str
    agent_name: str
    status: str
    output: str
    used_llm: bool
    model_profile: Optional[str] = None
    provider: Optional[str] = None
    created_at: datetime
    context: Dict[str, Any]


class ExecutionHistoryResponse(ApiSchema):
    executions: List[ExecutionResponse]


# ── Auth / API Keys ─────────────────────────────────────────────────────────

class ApiKeyCreateRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(pattern="^(admin|operator|viewer)$")


class ApiKeyResponse(ApiSchema):
    id: str
    name: str
    role: str
    created_at: datetime
    is_active: bool


class ApiKeyCreateResponse(ApiKeyResponse):
    key: str  # raw key shown exactly once at creation


class ApiKeyListResponse(ApiSchema):
    keys: List[ApiKeyResponse]


class ApiKeyBootstrapRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=100)


class AuthStatusResponse(ApiSchema):
    auth_enabled: bool
    bootstrap_required: bool


# ── Metrics ─────────────────────────────────────────────────────────────────

class AgentMetric(ApiSchema):
    agent_name: str
    total_executions: int
    llm_executions: int
    failed_executions: int
    last_executed_at: Optional[datetime] = None
    updated_at: datetime


class MetricsResponse(ApiSchema):
    metrics: List[AgentMetric]


# ── Logs ────────────────────────────────────────────────────────────────────

class LogEntry(ApiSchema):
    id: str
    level: str
    logger: str
    message: str
    agent_name: Optional[str] = None
    execution_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    timestamp: datetime


class LogsResponse(ApiSchema):
    logs: List[LogEntry]


# ── Workflows ────────────────────────────────────────────────────────────────

class WorkflowStepSchema(ApiSchema):
    task_template: str = Field(min_length=1, max_length=4000)
    agent_name: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinitionRequest(ApiSchema):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    steps: List[WorkflowStepSchema] = Field(min_length=1, max_length=20)


class WorkflowDefinitionResponse(ApiSchema):
    id: str
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStepSchema]
    created_by: Optional[str] = None
    created_at: datetime


class WorkflowDefinitionListResponse(ApiSchema):
    definitions: List[WorkflowDefinitionResponse]


class WorkflowExecuteRequest(ApiSchema):
    workflow_id: str
    initial_context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStepResult(ApiSchema):
    step_index: int
    agent_name: str
    output: str
    used_llm: bool
    execution_id: Optional[str] = None
    success: bool
    error: Optional[str] = None


class WorkflowExecutionResponse(ApiSchema):
    id: str
    workflow_id: str
    status: str
    current_step: int
    total_steps: int
    results: List[WorkflowStepResult]
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowExecutionListResponse(ApiSchema):
    executions: List[WorkflowExecutionResponse]


# ── Errors ───────────────────────────────────────────────────────────────────

class ApiError(ApiSchema):
    detail: str
