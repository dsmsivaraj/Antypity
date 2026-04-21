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


# ── Career / Resume / Jobs ──────────────────────────────────────────────────

class ResumeEvaluateRequest(ApiSchema):
    text: str = Field(min_length=1)
    jd_text: str = ""
    model_profile: Optional[str] = None


class ResumeDimensionScore(ApiSchema):
    score: int
    max: int
    notes: str


class ResumeEvaluationResponse(ApiSchema):
    overall_score: int
    grade: str
    ats_risk_level: str
    summary: str
    dimensions: Dict[str, Any]
    top_strengths: List[str]
    critical_fixes: List[str]
    missing_sections: List[str]
    used_llm: bool = False
    provider: Optional[str] = None


class ResumeWriteRequest(ApiSchema):
    resume_text: str = ""
    jd_text: str = ""
    target_role: str = Field(default="Software Engineer", min_length=2, max_length=200)
    section: str = "all"
    candidate_name: str = "Candidate"
    model_profile: Optional[str] = None


class ResumeWrittenContent(ApiSchema):
    professional_summary: str
    experience_bullets: List[str]
    skills_section: Dict[str, Any]
    objective_statement: str
    keywords_embedded: List[str]
    writing_notes: str


class ResumeWriteResponse(ApiSchema):
    target_role: str
    written_content: ResumeWrittenContent
    used_llm: bool = False
    provider: Optional[str] = None


class ResumeReviewRequest(ApiSchema):
    text: str = Field(min_length=1)
    jd_text: str = ""
    target_role: str = ""
    model_profile: Optional[str] = None


class ResumeSectionFeedback(ApiSchema):
    score: int
    feedback: str
    fixes: List[str]


class ResumeReviewResponse(ApiSchema):
    overall_verdict: str
    interview_probability: str
    sections: Dict[str, Any]
    top_3_immediate_actions: List[str]
    red_flags: List[str]
    interview_tips: List[str]
    used_llm: bool = False
    provider: Optional[str] = None


class JobHuntRequest(ApiSchema):
    resume_text: str = Field(min_length=50)
    location: str = "India"
    experience_years: float = 0
    top_count: int = Field(default=25, ge=10, le=50)
    model_profile: Optional[str] = None


class TailoredApplication(ApiSchema):
    company: str
    role: str
    apply_url: str
    fit_score: int
    tailored_content: Dict[str, Any]


class JobOpportunity(ApiSchema):
    id: str
    company: str
    role: str
    sector: str
    company_type: str
    location: str
    apply_url: str
    career_url: str
    fit_score: int
    package_lpa: str
    tier: str  # high | medium | stretch


class JobHuntResponse(ApiSchema):
    candidate_name: str
    target_roles: List[str]
    total_opportunities: int
    opportunities: List[JobOpportunity]
    high_tier: List[JobOpportunity]
    medium_tier: List[JobOpportunity]
    stretch_tier: List[JobOpportunity]
    tailored_applications: List[TailoredApplication]
    profile: Dict[str, Any]


class LiveJobResult(ApiSchema):
    id: str
    title: str
    company: str
    location: str
    url: str
    source: str
    source_label: str
    result_type: str = "listing"
    jd_snippet: str
    jd_full: str
    published: str = ""
    tier: str = "stretch"
    match_score: int = 0
    matched_keywords: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    improvement_areas: List[str] = Field(default_factory=list)
    ats_summary: str = ""


class LiveJobHuntRequest(ApiSchema):
    resume_text: str = Field(min_length=1)
    location: str = "India"
    experience_years: float = 0.0
    model_profile: Optional[str] = None


class LiveJobHuntResponse(ApiSchema):
    candidate_name: str
    target_roles: List[str]
    total_found: int
    jobs: List[LiveJobResult]
    high_tier: List[LiveJobResult]
    medium_tier: List[LiveJobResult]
    stretch_tier: List[LiveJobResult]


class ResumeParseResponse(ApiSchema):
    filename: str
    text: str
    metadata: Dict[str, Any]
    parsed_fields: Optional[Dict[str, Any]] = None


class ResumeAnalyzeRequest(ApiSchema):
    text: str = Field(min_length=1)
    jd_text: str = ""
    source_filename: Optional[str] = None
    model_profile: Optional[str] = None


class ResumeAnalysisResponse(ApiSchema):
    id: Optional[str] = None
    title: str
    source_filename: Optional[str] = None
    summary: str
    match_score: int
    suggestions: List[str]
    ats_keywords: List[str]
    strengths: List[str]
    gaps: List[str]
    recommended_roles: List[str]
    model_profile: Optional[str] = None
    used_llm: bool = False
    provider: Optional[str] = None
    created_at: Optional[datetime] = None


class ResumeChatRequest(ApiSchema):
    question: str = Field(min_length=2, max_length=2000)
    resume_text: str = Field(min_length=1)
    jd_text: str = ""
    model_profile: Optional[str] = None


class ResumeChatResponse(ApiSchema):
    answer: str
    used_llm: bool
    provider: str
    model_profile: str
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: str = "medium"
    suggested_questions: List[str]


class CoverLetterRequest(ApiSchema):
    resume_text: str = Field(min_length=1)
    jd_text: str = ""
    target_role: str = Field(min_length=2, max_length=200)
    company_name: str = Field(default="Hiring Team", min_length=2, max_length=200)
    hiring_manager_name: str = ""
    tone: str = "professional"
    model_profile: Optional[str] = None


class CoverLetterResponse(ApiSchema):
    company_name: str
    target_role: str
    subject_line: str
    cover_letter: str
    talking_points: List[str]
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: str = "medium"
    used_llm: bool
    provider: str
    model_profile: str


class RecruiterContactRequest(ApiSchema):
    company_name: str = Field(min_length=2, max_length=200)
    company_domain: str = ""
    job_url: str = ""
    source_text: str = ""
    target_role: str = ""


class RecruiterContact(ApiSchema):
    name: str
    title: str
    email: Optional[str] = None
    contact_url: Optional[str] = None
    source: str
    confidence: str
    notes: str


class RecruiterContactResponse(ApiSchema):
    company_name: str
    company_domain: Optional[str] = None
    contacts: List[RecruiterContact]
    lookup_urls: List[str]
    verified_contact_count: int = 0
    inferred_contact_count: int = 0
    confidence: str = "medium"
    provenance: List[str] = Field(default_factory=list)


class ResumeTemplateDesignRequest(ApiSchema):
    name: str = Field(min_length=2, max_length=120)
    target_role: str = Field(min_length=2, max_length=200)
    style: str = Field(min_length=2, max_length=120)
    notes: str = ""
    model_profile: Optional[str] = None


class ResumeTemplateResponse(ApiSchema):
    id: str
    name: str
    target_role: str
    style: str
    figma_prompt: str
    sections: List[str]
    design_tokens: Dict[str, str]
    preview_markdown: str
    source: str = "generated"
    model_profile: Optional[str] = None
    created_at: Optional[datetime] = None


class ResumeTemplateListResponse(ApiSchema):
    templates: List[ResumeTemplateResponse]


class JobSourceResponse(ApiSchema):
    id: str
    label: str
    hosts: List[str]
    search_url: str


class JobSourceListResponse(ApiSchema):
    sources: List[JobSourceResponse]


class JobDescriptionExtractRequest(ApiSchema):
    url: Optional[str] = None
    text: Optional[str] = None


class JobDescriptionResponse(ApiSchema):
    title: str
    company: str
    description: str
    source: str
    source_type: str
    keywords: List[str]
    citations: List[Dict[str, Any]] = Field(default_factory=list)
    confidence: str = "medium"


class JobSearchRequest(ApiSchema):
    keywords: List[str] = Field(min_length=1, max_length=20)
    locations: List[str] = Field(default_factory=list, max_length=10)
    sources: List[str] = Field(default_factory=list, max_length=10)


class JobSearchResult(ApiSchema):
    id: str
    title: str
    company: str
    location: str
    url: str
    source: str
    summary: str
    ats_score: Optional[float] = None


class CareerAnalyticsResponse(ApiSchema):
    total_resume_analyses: int
    total_templates: int
    total_job_queries: int
    total_job_results: int
    average_match_score: float
    top_sources: Dict[str, int]
    quality_total_evaluations: int = 0
    quality_avg_grounding_score: float = 0.0
    quality_avg_citation_count: float = 0.0
    quality_drift_alerts: int = 0


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


class PlatformInsightsResponse(ApiSchema):
    registered_agents: int
    model_profiles: int
    local_model_profiles: int
    metrics_rows: int
    total_agent_executions: int
    llm_execution_ratio: float
    postgres_configured: bool
    retrieval_backend: str
    retrieval_document_count: int
    retrieval_model_loaded: bool
    retrieval_total_queries: int = 0
    retrieval_hit_rate: float = 0.0
    retrieval_avg_latency_ms: float = 0.0
    retrieval_empty_context_rate: float = 0.0
    quality_total_evaluations: int = 0
    quality_avg_grounding_score: float = 0.0
    quality_avg_citation_count: float = 0.0
    quality_drift_alerts: int = 0
    self_healing_running: bool


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


# ── Diagnostics ──────────────────────────────────────────────────────────────

class DiagnosticIssue(ApiSchema):
    severity: str
    category: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None


class DiagnosticTestResult(ApiSchema):
    passed: int
    failed: int
    errors: int
    duration_seconds: float
    status: str
    output: str = ""


class DiagnosticRunResponse(ApiSchema):
    id: str
    status: str
    health: Optional[Dict[str, Any]] = None
    tests: Optional[DiagnosticTestResult] = None
    issues: List[DiagnosticIssue] = []
    summary: str
    created_at: datetime
    completed_at: Optional[datetime] = None


class DiagnosticRunListResponse(ApiSchema):
    runs: List[DiagnosticRunResponse]


# ── Chat ─────────────────────────────────────────────────────────────────────

class ChatMessage(ApiSchema):
    role: str
    content: str
    timestamp: Optional[str] = None


class ChatRequest(ApiSchema):
    message: str
    session_id: str = "default"
    resume_text: Optional[str] = None
    jd_text: Optional[str] = None


class ChatResponse(ApiSchema):
    session_id: str
    response: str
    provider: str
    used_llm: bool
    turn: int


class ChatHistoryResponse(ApiSchema):
    session_id: str
    messages: List[ChatMessage]


# ── Ollama status ─────────────────────────────────────────────────────────────

class OllamaStatusResponse(ApiSchema):
    enabled: bool
    base_url: str
    model: str
    detail: str
    available_models: List[str] = []


# ── Errors ───────────────────────────────────────────────────────────────────

class ApiError(ApiSchema):
    detail: str


# ── Google OAuth / User Profile ──────────────────────────────────────────────

class GoogleAuthRequest(ApiSchema):
    id_token: str


class UserResponse(ApiSchema):
    id: str
    email: str
    full_name: Optional[str] = None
    role: str
    status: str
    social_provider: Optional[str] = None
    created_at: Optional[datetime] = None


class TokenResponse(ApiSchema):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserProfileResponse(ApiSchema):
    user_id: str
    resume_data: Optional[Dict[str, Any]] = None
    preferences: Optional[Dict[str, Any]] = None
    updated_at: Optional[datetime] = None
