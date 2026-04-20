from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
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
    ExecutionHistoryResponse,
    ExecutionResponse,
    HealthResponse,
    LogEntry,
    LogsResponse,
    ModelCompletionRequest,
    ModelCompletionResponse,
    ModelListResponse,
    ModelSummary,
    MetricsResponse,
    ReadyResponse,
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
        yield
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
            llm_enabled=container.llm_client.enabled,
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


app = create_app()
