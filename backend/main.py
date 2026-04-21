from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import Depends, FastAPI, File, Header, HTTPException, Query, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware

from agents.workflow_engine import WorkflowStep

from .container import AppContainer, build_container

from .schemas import (
    AgentMetric,
    AgentExecutionRequest,
    AgentExecutionResponse,
    AgentScoreRequest,
    AgentScoreResponse,
    AgentSummary,
    ApiKeyBootstrapRequest,
    ApiKeyCreateRequest,
    ApiKeyCreateResponse,
    ApiKeyListResponse,
    ApiKeyResponse,
    AuthStatusResponse,
    CareerAnalyticsResponse,
    ChatHistoryResponse,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    DiagnosticIssue,
    DiagnosticRunListResponse,
    DiagnosticRunResponse,
    DiagnosticTestResult,
    ExecutionHistoryResponse,
    ExecutionResponse,
    HealthResponse,
    JobDescriptionExtractRequest,
    JobDescriptionResponse,
    JobSearchRequest,
    JobSearchResult,
    JobSourceListResponse,
    JobSourceResponse,
    LogEntry,
    LogsResponse,
    ModelCompletionRequest,
    ModelCompletionResponse,
    ModelListResponse,
    ModelSummary,
    MetricsResponse,
    OllamaStatusResponse,
    ReadyResponse,
    JobHuntRequest,
    JobHuntResponse,
    JobOpportunity,
    TailoredApplication,
    LiveJobHuntRequest,
    LiveJobHuntResponse,
    LiveJobResult,
    ResumeAnalyzeRequest,
    ResumeAnalysisResponse,
    ResumeChatRequest,
    ResumeChatResponse,
    ResumeEvaluateRequest,
    ResumeEvaluationResponse,
    ResumeParseResponse,
    ResumeReviewRequest,
    ResumeReviewResponse,
    ResumeTemplateDesignRequest,
    ResumeTemplateListResponse,
    ResumeTemplateResponse,
    ResumeWriteRequest,
    ResumeWriteResponse,
    TaskRequest,
    WorkflowDefinitionListResponse,
    WorkflowDefinitionRequest,
    WorkflowDefinitionResponse,
    WorkflowExecuteRequest,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowStepResult,
    WorkflowStepSchema,
)

_logger = logging.getLogger(__name__)


# ── Auth helpers ─────────────────────────────────────────────────────────────

def _get_container(request: Request) -> AppContainer:
    return request.app.state.container  # type: ignore[no-any-return]


def _get_principal(
    request: Request,
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
) -> dict:
    container: AppContainer = request.app.state.container
    if not container.settings.auth_enabled or not container.auth_service.enabled:
        return {"id": "anonymous", "name": "anonymous", "role": "admin"}
    if container.auth_service.bootstrap_required():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No API keys provisioned. Use /auth/bootstrap with a bootstrap token to create the first admin key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    principal = container.auth_service.validate_key(x_api_key)
    if not principal:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked API key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return principal


def _require(permission: str):
    def dependency(
        request: Request,
        principal: dict = Depends(_get_principal),
    ) -> dict:
        container: AppContainer = request.app.state.container
        container.auth_service.check_permission(principal, permission)
        return principal
    return dependency


def _require_internal(
    request: Request,
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
) -> bool:
    container: AppContainer = request.app.state.container
    if x_internal_token != container.settings.internal_api_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal token.")
    return True


# ── App factory ──────────────────────────────────────────────────────────────

def create_app(container: Optional[AppContainer] = None) -> FastAPI:
    _container = container if container is not None else build_container()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.container = _container
        _logger.info(
            "Actypity backend started (version=%s, storage=%s, auth=%s, llm=%s).",
            _container.settings.app_version,
            _container.settings.storage_backend,
            _container.settings.auth_enabled,
            _container.llm_client.enabled,
        )
        _container.scheduler.start()
        _container.self_healing.start()
        yield
        await _container.scheduler.stop()
        await _container.self_healing.stop()
        _logger.info("Actypity backend shutting down.")

    app = FastAPI(
        title=_container.settings.app_name,
        version=_container.settings.app_version,
        lifespan=lifespan,
    )
    app.state.container = _container
    _container.internal_api.bind_app(app)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_container.settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Self-Healing (Gateway to Orchestrator) ──────────────────────────

    @app.get("/self-healing/status", tags=["self-healing"])
    async def get_self_healing_status(
        request: Request,
        _: dict = Depends(_require("admin")),
    ):
        container: AppContainer = request.app.state.container
        return container.self_healing.get_status()

    @app.post("/self-healing/trigger", tags=["self-healing"])
    async def trigger_self_healing(
        request: Request,
        _: dict = Depends(_require("admin")),
    ):
        container: AppContainer = request.app.state.container
        result = await container.self_healing.run_cycle()
        return result

    # ── Identity Proxy ──────────────────────────────────────────────────

    @app.post("/auth/social", tags=["auth"])
    async def proxy_social_auth(request: Request, body: dict):
        url = os.environ.get("IDENTITY_SERVICE_URL", "http://localhost:9504")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(f"{url}/auth/social", json=body)
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                _logger.error("Social auth proxy failed: %s", exc)
                raise HTTPException(status_code=502, detail="Identity service unreachable.")

    @app.get("/users/me", tags=["users"])
    async def proxy_get_me(request: Request, token: str = Query(...)):
        url = os.environ.get("IDENTITY_SERVICE_URL", "http://localhost:9504")
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{url}/users/me", params={"token": token})
                response.raise_for_status()
                return response.json()
            except Exception as exc:
                _logger.error("Get me proxy failed: %s", exc)
                raise HTTPException(status_code=401, detail="Invalid session.")

    _register_routes(app)
    return app


# ── Routes ───────────────────────────────────────────────────────────────────

def _register_routes(app: FastAPI) -> None:

    # ── Meta (public) ─────────────────────────────────────────────────────

    @app.get("/", tags=["meta"])
    async def root(request: Request):
        container: AppContainer = request.app.state.container
        return {
            "message": "Actypity backend is running.",
            "version": container.settings.app_version,
            "docs": "/docs",
        }

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    async def health(request: Request):
        container: AppContainer = request.app.state.container
        return HealthResponse(
            status="ok",
            service=container.settings.app_name,
            version=container.settings.app_version,
            llm_enabled=container.gemini_client.enabled or container.llm_client.enabled or container.ollama_client.enabled,
            storage_backend=container.settings.storage_backend,
            auth_enabled=container.settings.auth_enabled,
            auth_bootstrap_required=container.auth_service.bootstrap_required(),
            timestamp=datetime.now(timezone.utc),
        )

    @app.get("/ready", response_model=ReadyResponse, tags=["meta"])
    async def ready(request: Request):
        container: AppContainer = request.app.state.container
        checks = {
            "registry": "ok" if container.registry.list_names() else "empty",
            "storage": "ok",
            "llm": "configured" if container.llm_client.enabled else "optional",
            "auth": "enabled" if container.auth_service.enabled else "disabled",
        }
        if container.settings.storage_backend == "postgres":
            db_status = container.database_client.get_status()
            checks["database"] = "ok" if db_status.connected else db_status.detail
        database_ok = checks.get("database", "ok") == "ok"
        overall = "ready" if checks["registry"] == "ok" and database_ok else "degraded"
        return ReadyResponse(status=overall, checks=checks)

    # ── Agents (protected: agents:read) ──────────────────────────────────

    @app.get("/agents", response_model=list[AgentSummary], tags=["agents"])
    async def list_agents(
        request: Request,
        _: dict = Depends(_require("agents:read")),
    ):
        container: AppContainer = request.app.state.container
        if container.database_client.is_configured:
            try:
                records = container.database_client.list_agent_registry()
                if records:
                    return [
                        AgentSummary(
                            name=r["name"],
                            description=r["description"],
                            capabilities=list(r.get("capabilities") or []),
                            supports_tools=bool(r.get("supports_tools")),
                        )
                        for r in records
                    ]
            except Exception as exc:
                _logger.warning("Falling back to in-memory agent registry listing: %s", exc)
        return [
            AgentSummary(
                name=m.name,
                description=m.description,
                capabilities=m.capabilities,
                supports_tools=m.supports_tools,
                preferred_model=m.preferred_model,
            )
            for m in container.registry.list_metadata()
        ]

    @app.get("/models", response_model=ModelListResponse, tags=["models"])
    async def list_models(
        request: Request,
        _: dict = Depends(_require("agents:read")),
    ):
        container: AppContainer = request.app.state.container
        return ModelListResponse(
            models=[
                ModelSummary(
                    id=profile.id,
                    provider=profile.provider,
                    mode=profile.mode,
                    description=profile.description,
                    deployment=profile.deployment,
                )
                for profile in container.model_router.list_profiles()
            ]
        )

    # ── Executions ────────────────────────────────────────────────────────

    @app.get("/executions", response_model=ExecutionHistoryResponse, tags=["executions"])
    async def list_executions(
        request: Request,
        limit: int = Query(20, ge=1, le=100),
        _: dict = Depends(_require("executions:read")),
    ):
        container: AppContainer = request.app.state.container
        records = container.store.list_recent(limit=limit)
        return ExecutionHistoryResponse(
            executions=[
                ExecutionResponse(
                    execution_id=r["execution_id"],
                    agent_name=r["agent_name"],
                    status=r["status"],
                    output=r["output"],
                    used_llm=r["used_llm"],
                    model_profile=r.get("model_profile"),
                    provider=r.get("provider"),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    context=r.get("context", {}),
                )
                for r in records
            ]
        )

    @app.post("/execute", response_model=ExecutionResponse, tags=["executions"])
    async def execute_task(
        request: Request,
        body: TaskRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        try:
            result = await container.orchestrator.orchestrate(
                task=body.task,
                agent_name=body.agent_name,
                model_profile=body.model_profile,
                context=body.context,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Task execution failed.") from exc

        return ExecutionResponse(
            execution_id=result.execution_id,
            agent_name=result.agent_name,
            status=result.status,
            output=result.output,
            used_llm=result.used_llm,
            model_profile=result.model_profile,
            provider=result.provider,
            created_at=result.created_at,
            context=result.context,
        )

    # ── Auth / API Keys (admin only) ──────────────────────────────────────

    @app.post(
        "/auth/bootstrap",
        response_model=ApiKeyCreateResponse,
        status_code=201,
        tags=["auth"],
    )
    async def bootstrap_api_key(
        request: Request,
        body: ApiKeyBootstrapRequest,
        x_bootstrap_token: Optional[str] = Header(None, alias="X-Bootstrap-Token"),
    ):
        container: AppContainer = request.app.state.container
        if not container.auth_service.enabled:
            raise HTTPException(status_code=503, detail="Auth is disabled.")
        if not x_bootstrap_token:
            raise HTTPException(status_code=401, detail="Missing X-Bootstrap-Token header.")
        try:
            record = container.auth_service.bootstrap_admin(
                provided_token=x_bootstrap_token,
                configured_token=container.settings.bootstrap_admin_token,
                name=body.name,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApiKeyCreateResponse(**record)

    @app.get("/auth/status", response_model=AuthStatusResponse, tags=["auth"])
    async def auth_status(request: Request):
        container: AppContainer = request.app.state.container
        return AuthStatusResponse(
            auth_enabled=container.settings.auth_enabled and container.auth_service.enabled,
            bootstrap_required=container.auth_service.bootstrap_required(),
        )

    @app.post(
        "/auth/keys",
        response_model=ApiKeyCreateResponse,
        status_code=201,
        tags=["auth"],
    )
    async def create_api_key(
        request: Request,
        body: ApiKeyCreateRequest,
        _: dict = Depends(_require("keys:manage")),
    ):
        container: AppContainer = request.app.state.container
        if not container.auth_service.enabled:
            raise HTTPException(
                status_code=503,
                detail="Auth is disabled — PostgreSQL must be configured to manage API keys.",
            )
        try:
            record = container.auth_service.create_key(name=body.name, role=body.role)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ApiKeyCreateResponse(**record)

    @app.get("/auth/keys", response_model=ApiKeyListResponse, tags=["auth"])
    async def list_api_keys(
        request: Request,
        _: dict = Depends(_require("keys:manage")),
    ):
        container: AppContainer = request.app.state.container
        if not container.auth_service.enabled:
            return ApiKeyListResponse(keys=[])
        records = container.database_client.list_api_keys()
        return ApiKeyListResponse(
            keys=[ApiKeyResponse(**r) for r in records]
        )

    @app.delete("/auth/keys/{key_id}", status_code=204, tags=["auth"])
    async def revoke_api_key(
        request: Request,
        key_id: str,
        _: dict = Depends(_require("keys:manage")),
    ):
        container: AppContainer = request.app.state.container
        if not container.auth_service.enabled:
            raise HTTPException(status_code=503, detail="Auth is disabled.")
        removed = container.database_client.deactivate_api_key(key_id)
        if not removed:
            raise HTTPException(status_code=404, detail=f"Key '{key_id}' not found.")

    # ── Metrics ───────────────────────────────────────────────────────────

    @app.get("/metrics", response_model=MetricsResponse, tags=["metrics"])
    async def list_metrics(
        request: Request,
        _: dict = Depends(_require("metrics:read")),
    ):
        container: AppContainer = request.app.state.container
        records = container.metrics_service.list_all()
        return MetricsResponse(
            metrics=[AgentMetric(**r) for r in records]
        )

    # ── Logs ──────────────────────────────────────────────────────────────

    @app.get("/logs", response_model=LogsResponse, tags=["logs"])
    async def list_logs(
        request: Request,
        limit: int = Query(50, ge=1, le=500),
        level: Optional[str] = Query(None, description="Filter by log level: DEBUG, INFO, WARNING, ERROR"),
        execution_id: Optional[str] = Query(None),
        _: dict = Depends(_require("logs:read")),
    ):
        container: AppContainer = request.app.state.container
        if not container.database_client.is_configured:
            return LogsResponse(logs=[])
        records = container.database_client.list_logs(
            limit=limit, level=level, execution_id=execution_id
        )
        return LogsResponse(
            logs=[
                LogEntry(
                    id=r["id"],
                    level=r["level"],
                    logger=r["logger"],
                    message=r["message"],
                    agent_name=r.get("agent_name"),
                    execution_id=r.get("execution_id"),
                    extra=r.get("extra"),
                    timestamp=datetime.fromisoformat(r["timestamp"]),
                )
                for r in records
            ]
        )

    # ── Workflows ─────────────────────────────────────────────────────────

    @app.post(
        "/workflows/definitions",
        response_model=WorkflowDefinitionResponse,
        status_code=201,
        tags=["workflows"],
    )
    async def create_workflow_definition(
        request: Request,
        body: WorkflowDefinitionRequest,
        principal: dict = Depends(_require("workflows:execute")),
    ):
        container: AppContainer = request.app.state.container
        if not container.database_client.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Workflow definitions require PostgreSQL storage.",
            )
        steps_raw = [s.model_dump() for s in body.steps]
        try:
            record = container.database_client.save_workflow_definition(
                name=body.name,
                description=body.description,
                steps=steps_raw,
                created_by=principal.get("name"),
            )
        except Exception as exc:
            _logger.error("Failed to save workflow definition: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to save workflow definition.") from exc

        return WorkflowDefinitionResponse(
            id=record["id"],
            name=record["name"],
            description=record.get("description"),
            steps=[WorkflowStepSchema(**s) for s in record["steps"]],
            created_by=record.get("created_by"),
            created_at=datetime.fromisoformat(record["created_at"]),
        )

    @app.get(
        "/workflows/definitions",
        response_model=WorkflowDefinitionListResponse,
        tags=["workflows"],
    )
    async def list_workflow_definitions(
        request: Request,
        _: dict = Depends(_require("workflows:read")),
    ):
        container: AppContainer = request.app.state.container
        if not container.database_client.is_configured:
            return WorkflowDefinitionListResponse(definitions=[])
        records = container.database_client.list_workflow_definitions()
        return WorkflowDefinitionListResponse(
            definitions=[
                WorkflowDefinitionResponse(
                    id=r["id"],
                    name=r["name"],
                    description=r.get("description"),
                    steps=[WorkflowStepSchema(**s) for s in r["steps"]],
                    created_by=r.get("created_by"),
                    created_at=datetime.fromisoformat(r["created_at"]),
                )
                for r in records
            ]
        )

    @app.post(
        "/workflows/execute",
        response_model=WorkflowExecutionResponse,
        tags=["workflows"],
    )
    async def execute_workflow(
        request: Request,
        body: WorkflowExecuteRequest,
        _: dict = Depends(_require("workflows:execute")),
    ):
        container: AppContainer = request.app.state.container
        if not container.database_client.is_configured:
            raise HTTPException(
                status_code=503,
                detail="Workflow execution requires PostgreSQL storage.",
            )

        definition = container.database_client.get_workflow_definition(body.workflow_id)
        if not definition:
            raise HTTPException(
                status_code=404,
                detail=f"Workflow definition '{body.workflow_id}' not found.",
            )

        steps = [
            WorkflowStep(
                task_template=s["task_template"],
                agent_name=s.get("agent_name"),
                context=s.get("context", {}),
            )
            for s in definition["steps"]
        ]

        wf_exec = container.database_client.create_workflow_execution(
            workflow_id=body.workflow_id,
            total_steps=len(steps),
        )

        result = await container.workflow_executor.execute(
            workflow_id=body.workflow_id,
            execution_id=wf_exec["id"],
            steps=steps,
            initial_context=body.initial_context,
        )

        container.database_client.update_workflow_execution(
            execution_id=wf_exec["id"],
            status=result.status,
            current_step=len(result.steps),
            results=[s.as_dict() for s in result.steps],
            error=result.error,
        )

        return WorkflowExecutionResponse(
            id=wf_exec["id"],
            workflow_id=body.workflow_id,
            status=result.status,
            current_step=len(result.steps),
            total_steps=len(steps),
            results=[WorkflowStepResult(**s.as_dict()) for s in result.steps],
            error=result.error,
            created_at=datetime.fromisoformat(wf_exec["created_at"]),
            completed_at=datetime.now(timezone.utc),
        )

    @app.get(
        "/workflows/executions",
        response_model=WorkflowExecutionListResponse,
        tags=["workflows"],
    )
    async def list_workflow_executions(
        request: Request,
        limit: int = Query(20, ge=1, le=100),
        _: dict = Depends(_require("workflows:read")),
    ):
        container: AppContainer = request.app.state.container
        if not container.database_client.is_configured:
            return WorkflowExecutionListResponse(executions=[])
        records = container.database_client.list_workflow_executions(limit=limit)
        return WorkflowExecutionListResponse(
            executions=[
                WorkflowExecutionResponse(
                    id=r["id"],
                    workflow_id=r["workflow_id"],
                    status=r["status"],
                    current_step=r["current_step"],
                    total_steps=r["total_steps"],
                    results=[WorkflowStepResult(**s) for s in (r.get("results") or [])],
                    error=r.get("error"),
                    created_at=datetime.fromisoformat(r["created_at"]),
                    completed_at=(
                        datetime.fromisoformat(r["completed_at"])
                        if r.get("completed_at")
                        else None
                    ),
                )
                for r in records
            ]
        )

    # ── Diagnostics ───────────────────────────────────────────────────────

    @app.post("/diagnostics/run", response_model=DiagnosticRunResponse, tags=["diagnostics"])
    async def run_diagnostics(
        request: Request,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        record = await container.diagnostics_service.run_full_diagnostics()
        return _build_diag_response(record)

    @app.get("/diagnostics/reports", response_model=DiagnosticRunListResponse, tags=["diagnostics"])
    async def list_diagnostic_reports(
        request: Request,
        limit: int = Query(10, ge=1, le=50),
        _: dict = Depends(_require("logs:read")),
    ):
        container: AppContainer = request.app.state.container
        records = container.diagnostics_service.get_reports(limit=limit)
        return DiagnosticRunListResponse(runs=[_build_diag_response(r) for r in records])

    @app.get("/diagnostics/reports/latest", response_model=DiagnosticRunResponse, tags=["diagnostics"])
    async def latest_diagnostic_report(
        request: Request,
        _: dict = Depends(_require("logs:read")),
    ):
        container: AppContainer = request.app.state.container
        record = container.diagnostics_service.get_latest_report()
        if not record:
            raise HTTPException(status_code=404, detail="No diagnostic reports found. Run POST /diagnostics/run first.")
        return _build_diag_response(record)

    # ── Career features ───────────────────────────────────────────────────

    @app.post("/resume/parse", response_model=ResumeParseResponse, tags=["resume"])
    async def parse_resume_file(
        request: Request,
        file: UploadFile = File(...),
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        content = await file.read()
        try:
            parsed = container.career_service.parse_resume(file.filename or "resume.txt", content)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return ResumeParseResponse(
            filename=parsed.filename,
            text=parsed.text,
            metadata=parsed.metadata,
        )

    @app.post("/resume/analyze", response_model=ResumeAnalysisResponse, tags=["resume"])
    async def analyze_resume(
        request: Request,
        body: ResumeAnalyzeRequest,
        principal: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        record = container.career_service.analyze_resume(
            resume_text=body.text,
            jd_text=body.jd_text,
            model_profile=body.model_profile,
            source_filename=body.source_filename,
            created_by=principal.get("name"),
        )
        return ResumeAnalysisResponse(
            id=record.get("id"),
            title=record["title"],
            source_filename=record.get("source_filename"),
            summary=record["summary"],
            match_score=int(record["match_score"]),
            suggestions=list(record.get("suggestions") or []),
            ats_keywords=list(record.get("ats_keywords") or []),
            strengths=list(record.get("strengths") or []),
            gaps=list(record.get("gaps") or []),
            recommended_roles=list(record.get("recommended_roles") or []),
            model_profile=record.get("model_profile"),
            used_llm=bool(record.get("used_llm")),
            provider=record.get("provider"),
            created_at=(
                datetime.fromisoformat(record["created_at"])
                if record.get("created_at")
                else None
            ),
        )

    @app.post("/resume/chat", response_model=ResumeChatResponse, tags=["resume"])
    async def resume_chat(
        request: Request,
        body: ResumeChatRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        result = container.career_service.chat_resume(
            question=body.question,
            resume_text=body.resume_text,
            jd_text=body.jd_text,
            model_profile=body.model_profile,
        )
        return ResumeChatResponse(**result)

    @app.get("/resume/templates", response_model=ResumeTemplateListResponse, tags=["resume"])
    async def list_resume_templates(
        request: Request,
        _: dict = Depends(_require("agents:read")),
    ):
        container: AppContainer = request.app.state.container
        templates = container.career_service.list_templates()
        return ResumeTemplateListResponse(
            templates=[
                ResumeTemplateResponse(
                    id=t["id"],
                    name=t["name"],
                    target_role=t["target_role"],
                    style=t["style"],
                    figma_prompt=t["figma_prompt"],
                    sections=list(t.get("sections") or []),
                    design_tokens=dict(t.get("design_tokens") or {}),
                    preview_markdown=t["preview_markdown"],
                    source=t.get("source", "generated"),
                    model_profile=t.get("model_profile"),
                    created_at=(
                        datetime.fromisoformat(t["created_at"])
                        if t.get("created_at")
                        else None
                    ),
                )
                for t in templates
            ]
        )

    @app.post("/resume/templates/design", response_model=ResumeTemplateResponse, tags=["resume"])
    async def design_resume_template(
        request: Request,
        body: ResumeTemplateDesignRequest,
        principal: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        template = container.career_service.design_template(
            name=body.name,
            target_role=body.target_role,
            style=body.style,
            notes=body.notes,
            model_profile=body.model_profile,
            created_by=principal.get("name"),
        )
        return ResumeTemplateResponse(
            id=template["id"],
            name=template["name"],
            target_role=template["target_role"],
            style=template["style"],
            figma_prompt=template["figma_prompt"],
            sections=list(template.get("sections") or []),
            design_tokens=dict(template.get("design_tokens") or {}),
            preview_markdown=template["preview_markdown"],
            source=template.get("source", "generated"),
            model_profile=template.get("model_profile"),
            created_at=(
                datetime.fromisoformat(template["created_at"])
                if template.get("created_at")
                else None
            ),
        )

    @app.get("/job/sources", response_model=JobSourceListResponse, tags=["jobs"])
    async def list_job_sources(
        request: Request,
        _: dict = Depends(_require("agents:read")),
    ):
        container: AppContainer = request.app.state.container
        return JobSourceListResponse(
            sources=[JobSourceResponse(**source) for source in container.career_service.trusted_sources()]
        )

    @app.post("/job/extract", response_model=JobDescriptionResponse, tags=["jobs"])
    async def extract_job_description(
        request: Request,
        body: JobDescriptionExtractRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        try:
            result = await container.career_service.extract_job_description(url=body.url, text=body.text)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except httpx.HTTPError as exc:
            raise HTTPException(status_code=502, detail=f"Failed to fetch job description: {exc}") from exc
        return JobDescriptionResponse(**result)

    @app.post("/job/search", response_model=list[JobSearchResult], tags=["jobs"])
    async def search_jobs(
        request: Request,
        body: JobSearchRequest,
        principal: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        try:
            results = container.career_service.search_jobs(
                keywords=body.keywords,
                locations=body.locations,
                sources=body.sources,
                created_by=principal.get("name"),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return [
            JobSearchResult(
                id=item["id"],
                title=item["title"],
                company=item["company"],
                location=item["location"],
                url=item["url"],
                source=item["source"],
                summary=item["summary"],
                ats_score=item.get("ats_score"),
            )
            for item in results
        ]

    @app.post("/resume/evaluate", response_model=ResumeEvaluationResponse, tags=["resume"])
    async def evaluate_resume(
        request: Request,
        body: ResumeEvaluateRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        result = container.career_service.evaluate_resume(
            resume_text=body.text,
            jd_text=body.jd_text,
            model_profile=body.model_profile,
        )
        return ResumeEvaluationResponse(**result)

    @app.post("/resume/write", response_model=ResumeWriteResponse, tags=["resume"])
    async def write_resume(
        request: Request,
        body: ResumeWriteRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        result = container.career_service.write_resume(
            resume_text=body.resume_text,
            jd_text=body.jd_text,
            target_role=body.target_role,
            section=body.section,
            candidate_name=body.candidate_name,
            model_profile=body.model_profile,
        )
        return ResumeWriteResponse(**result)

    @app.post("/resume/review", response_model=ResumeReviewResponse, tags=["resume"])
    async def review_resume(
        request: Request,
        body: ResumeReviewRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        result = container.career_service.review_resume(
            resume_text=body.text,
            jd_text=body.jd_text,
            target_role=body.target_role,
            model_profile=body.model_profile,
        )
        return ResumeReviewResponse(**result)

    @app.post("/jobs/hunt", response_model=JobHuntResponse, tags=["jobs"])
    async def hunt_jobs(
        request: Request,
        body: JobHuntRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        result = container.career_service.hunt_jobs(
            resume_text=body.resume_text,
            location=body.location,
            experience_years=body.experience_years,
            top_count=body.top_count,
            model_profile=body.model_profile,
        )
        opps = [JobOpportunity(**o) for o in result["opportunities"]]
        return JobHuntResponse(
            candidate_name=result["candidate_name"],
            target_roles=result["target_roles"],
            total_opportunities=result["total_opportunities"],
            opportunities=opps,
            high_tier=[JobOpportunity(**o) for o in result["high_tier"]],
            medium_tier=[JobOpportunity(**o) for o in result["medium_tier"]],
            stretch_tier=[JobOpportunity(**o) for o in result["stretch_tier"]],
            tailored_applications=[TailoredApplication(**t) for t in result["tailored_applications"]],
            profile=result["profile"],
        )

    @app.post("/jobs/live-hunt", response_model=LiveJobHuntResponse, tags=["jobs"])
    async def live_hunt_jobs(
        request: Request,
        body: LiveJobHuntRequest,
        _: dict = Depends(_require("execute")),
    ):
        container: AppContainer = request.app.state.container
        result = await container.career_service.live_hunt_jobs(
            resume_text=body.resume_text,
            location=body.location,
            experience_years=body.experience_years,
            model_profile=body.model_profile,
        )
        def _to_live(j: dict) -> LiveJobResult:
            return LiveJobResult(**{k: j[k] for k in LiveJobResult.model_fields if k in j})
        return LiveJobHuntResponse(
            candidate_name=result["candidate_name"],
            target_roles=result["target_roles"],
            total_found=result["total_found"],
            jobs=[_to_live(j) for j in result["jobs"]],
            high_tier=[_to_live(j) for j in result["high_tier"]],
            medium_tier=[_to_live(j) for j in result["medium_tier"]],
            stretch_tier=[_to_live(j) for j in result["stretch_tier"]],
        )

    @app.get("/tracker/analytics", response_model=CareerAnalyticsResponse, tags=["analytics"])
    async def tracker_analytics(
        request: Request,
        _: dict = Depends(_require("metrics:read")),
    ):
        container: AppContainer = request.app.state.container
        return CareerAnalyticsResponse(**container.career_service.analytics())

    # ── Chatbot ───────────────────────────────────────────────────────────

    @app.post("/chat", response_model=ChatResponse, tags=["chat"])
    async def chat(request: Request, body: ChatRequest):
        container: AppContainer = request.app.state.container
        result = container.registry.get("career-chatbot")
        if result is None:
            raise HTTPException(status_code=503, detail="Chatbot agent not available.")
        agent_result = result.execute(
            body.message,
            context={
                "session_id": body.session_id,
                "resume_text": body.resume_text or "",
                "jd_text": body.jd_text or "",
            },
        )
        return ChatResponse(
            session_id=agent_result.metadata.get("session_id", body.session_id),
            response=agent_result.output,
            provider=agent_result.metadata.get("provider", "unknown"),
            used_llm=agent_result.used_llm,
            turn=agent_result.metadata.get("turn", 1),
        )

    @app.get("/chat/history/{session_id}", response_model=ChatHistoryResponse, tags=["chat"])
    async def chat_history(request: Request, session_id: str):
        container: AppContainer = request.app.state.container
        messages = container.chat_store.get_history(session_id)
        return ChatHistoryResponse(
            session_id=session_id,
            messages=[ChatMessage(role=m["role"], content=m["content"], timestamp=m.get("timestamp")) for m in messages],
        )

    @app.delete("/chat/session/{session_id}", tags=["chat"])
    async def clear_chat_session(request: Request, session_id: str):
        container: AppContainer = request.app.state.container
        container.chat_store.clear(session_id)
        return {"cleared": True, "session_id": session_id}

    # ── Ollama / local model status ───────────────────────────────────────

    @app.get("/ollama/status", response_model=OllamaStatusResponse, tags=["local-llm"])
    async def ollama_status(request: Request):
        container: AppContainer = request.app.state.container
        ol = container.ollama_client
        return OllamaStatusResponse(
            enabled=ol.enabled,
            base_url=ol.base_url,
            model=ol.model,
            detail=ol._availability_detail,
            available_models=ol.list_local_models(),
        )

    # ── Internal orchestration APIs ──────────────────────────────────────

    @app.get("/internal/models", response_model=ModelListResponse, include_in_schema=False)
    async def internal_models(
        request: Request,
        _: bool = Depends(_require_internal),
    ):
        container: AppContainer = request.app.state.container
        return ModelListResponse(
            models=[
                ModelSummary(
                    id=profile.id,
                    provider=profile.provider,
                    mode=profile.mode,
                    description=profile.description,
                    deployment=profile.deployment,
                )
                for profile in container.model_router.list_profiles()
            ]
        )

    @app.post("/internal/models/complete", response_model=ModelCompletionResponse, include_in_schema=False)
    async def internal_complete_model(
        request: Request,
        body: ModelCompletionRequest,
        _: bool = Depends(_require_internal),
    ):
        container: AppContainer = request.app.state.container
        profile, llm_result = container.model_router.complete(
            model_profile=body.model_profile,
            prompt=body.prompt,
            system_prompt=body.system_prompt,
        )
        return ModelCompletionResponse(
            content=llm_result.content,
            used_llm=llm_result.used_llm,
            provider=llm_result.provider,
            model_profile=profile.id,
        )

    @app.post("/internal/agents/{agent_name}/score", response_model=AgentScoreResponse, include_in_schema=False)
    async def internal_agent_score(
        request: Request,
        agent_name: str,
        body: AgentScoreRequest,
        _: bool = Depends(_require_internal),
    ):
        container: AppContainer = request.app.state.container
        agent = container.registry.get(agent_name)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_name}'.")
        return AgentScoreResponse(
            agent_name=agent.name,
            score=agent.can_handle(body.task, body.context),
        )

    @app.post("/internal/agents/{agent_name}/execute", response_model=AgentExecutionResponse, include_in_schema=False)
    async def internal_agent_execute(
        request: Request,
        agent_name: str,
        body: AgentExecutionRequest,
        _: bool = Depends(_require_internal),
    ):
        container: AppContainer = request.app.state.container
        agent = container.registry.get(agent_name)
        if agent is None:
            raise HTTPException(status_code=404, detail=f"Unknown agent '{agent_name}'.")

        prompt_bundle = agent.build_prompt(body.task, body.context)
        if prompt_bundle is None:
            result = agent.execute(body.task, body.context)
            return AgentExecutionResponse(
                agent_name=agent.name,
                output=result.output,
                used_llm=result.used_llm,
                provider=str(result.metadata.get("provider", "deterministic")),
                model_profile=body.model_profile or agent.preferred_model,
            )

        profile, llm_result = container.model_router.complete(
            model_profile=body.model_profile or agent.preferred_model,
            prompt=prompt_bundle["prompt"],
            system_prompt=prompt_bundle.get("system_prompt"),
        )
        return AgentExecutionResponse(
            agent_name=agent.name,
            output=llm_result.content,
            used_llm=llm_result.used_llm,
            provider=llm_result.provider,
            model_profile=profile.id,
        )


def _build_diag_response(record: dict) -> DiagnosticRunResponse:
    tests_raw = record.get("tests")
    tests_model = None
    if tests_raw:
        tests_model = DiagnosticTestResult(
            passed=tests_raw.get("passed", 0),
            failed=tests_raw.get("failed", 0),
            errors=tests_raw.get("errors", 0),
            duration_seconds=float(tests_raw.get("duration_seconds", 0)),
            status=tests_raw.get("status", "unknown"),
            output=tests_raw.get("output", ""),
        )
    return DiagnosticRunResponse(
        id=record["id"],
        status=record["status"],
        health=record.get("health"),
        tests=tests_model,
        issues=[DiagnosticIssue(**i) for i in (record.get("issues") or [])],
        summary=record["summary"],
        created_at=datetime.fromisoformat(record["created_at"]),
        completed_at=(
            datetime.fromisoformat(record["completed_at"])
            if record.get("completed_at") else None
        ),
    )


app = create_app()
