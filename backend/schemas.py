from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Health / Ready ──────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    llm_enabled: bool
    storage_backend: str
    auth_enabled: bool
    auth_bootstrap_required: bool
    timestamp: datetime


class ReadyResponse(BaseModel):
    status: str
    checks: Dict[str, str]


# ── Agents ──────────────────────────────────────────────────────────────────

class AgentSummary(BaseModel):
    name: str
    description: str
    capabilities: List[str]
    supports_tools: bool = False


# ── Executions ──────────────────────────────────────────────────────────────

class TaskRequest(BaseModel):
    task: str = Field(min_length=3, max_length=4000)
    agent_name: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class ExecutionResponse(BaseModel):
    execution_id: str
    agent_name: str
    status: str
    output: str
    used_llm: bool
    created_at: datetime
    context: Dict[str, Any]


class ExecutionHistoryResponse(BaseModel):
    executions: List[ExecutionResponse]


# ── Auth / API Keys ─────────────────────────────────────────────────────────

class ApiKeyCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    role: str = Field(pattern="^(admin|operator|viewer)$")


class ApiKeyResponse(BaseModel):
    id: str
    name: str
    role: str
    created_at: datetime
    is_active: bool


class ApiKeyCreateResponse(ApiKeyResponse):
    key: str  # raw key shown exactly once at creation


class ApiKeyListResponse(BaseModel):
    keys: List[ApiKeyResponse]


class ApiKeyBootstrapRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)


class AuthStatusResponse(BaseModel):
    auth_enabled: bool
    bootstrap_required: bool


# ── Metrics ─────────────────────────────────────────────────────────────────

class AgentMetric(BaseModel):
    agent_name: str
    total_executions: int
    llm_executions: int
    failed_executions: int
    last_executed_at: Optional[datetime] = None
    updated_at: datetime


class MetricsResponse(BaseModel):
    metrics: List[AgentMetric]


# ── Logs ────────────────────────────────────────────────────────────────────

class LogEntry(BaseModel):
    id: str
    level: str
    logger: str
    message: str
    agent_name: Optional[str] = None
    execution_id: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None
    timestamp: datetime


class LogsResponse(BaseModel):
    logs: List[LogEntry]


# ── Workflows ────────────────────────────────────────────────────────────────

class WorkflowStepSchema(BaseModel):
    task_template: str = Field(min_length=1, max_length=4000)
    agent_name: Optional[str] = None
    context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowDefinitionRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    steps: List[WorkflowStepSchema] = Field(min_length=1, max_length=20)


class WorkflowDefinitionResponse(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    steps: List[WorkflowStepSchema]
    created_by: Optional[str] = None
    created_at: datetime


class WorkflowDefinitionListResponse(BaseModel):
    definitions: List[WorkflowDefinitionResponse]


class WorkflowExecuteRequest(BaseModel):
    workflow_id: str
    initial_context: Dict[str, Any] = Field(default_factory=dict)


class WorkflowStepResult(BaseModel):
    step_index: int
    agent_name: str
    output: str
    used_llm: bool
    success: bool
    error: Optional[str] = None


class WorkflowExecutionResponse(BaseModel):
    id: str
    workflow_id: str
    status: str
    current_step: int
    total_steps: int
    results: List[WorkflowStepResult]
    error: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None


class WorkflowExecutionListResponse(BaseModel):
    executions: List[WorkflowExecutionResponse]


# ── Errors ───────────────────────────────────────────────────────────────────

class ApiError(BaseModel):
    detail: str
