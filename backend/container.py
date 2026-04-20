from __future__ import annotations

import logging
from dataclasses import dataclass

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.diagnostics_agent import (
    CodeAnalyzerAgent,
    DiagnosticsReporterAgent,
    HealthCheckAgent,
    TestRunnerAgent,
)
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from agents.workflow_engine import WorkflowExecutor

from .auth import AuthService
from .config import Settings, get_settings
from .database import PostgreSQLDatabaseClient
from .diagnostics import DiagnosticsService
from .internal_api import InternalPlatformAPI
from .llm_client import LLMClient
from .log_handler import setup_logging
from .metrics import MetricsService
from .model_router import ModelRouter
from .scheduler import DiagnosticsScheduler
from .storage import ExecutionStore, build_execution_store

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AppContainer:
    settings: Settings
    llm_client: LLMClient
    model_router: ModelRouter
    internal_api: InternalPlatformAPI
    registry: AgentRegistry
    orchestrator: AgentOrchestrator
    store: ExecutionStore
    database_client: PostgreSQLDatabaseClient
    auth_service: AuthService
    metrics_service: MetricsService
    workflow_executor: WorkflowExecutor
    diagnostics_service: DiagnosticsService
    scheduler: DiagnosticsScheduler


def build_container() -> AppContainer:
    settings = get_settings()

    database_client = PostgreSQLDatabaseClient(settings)

    # Configure logging early so startup events are captured.
    setup_logging(database_client)

    llm_client = LLMClient(settings)
    model_router = ModelRouter(settings=settings, llm_client=llm_client)
    internal_api = InternalPlatformAPI(internal_token=settings.internal_api_token)
    metrics_service = MetricsService(db=database_client if database_client.is_configured else None)
    auth_service = AuthService(db=database_client, config_enabled=settings.auth_enabled)

    registry = AgentRegistry()
    registry.register(GeneralistAgent(llm_client=llm_client, skills=common_skills))
    registry.register(PlannerAgent(llm_client=llm_client, skills=common_skills))
    registry.register(ReviewerAgent(llm_client=llm_client, skills=common_skills))
    registry.register(MathAgent(skills=common_skills))

    store = build_execution_store(settings, database_client=database_client)
    orchestrator = AgentOrchestrator(
        registry=registry,
        store=store,
        internal_api=internal_api,
        metrics=metrics_service,
    )
    workflow_executor = WorkflowExecutor(orchestrator=orchestrator)

    # Register diagnostic agents
    health_agent = HealthCheckAgent(
        db_client=database_client, llm_client=llm_client, registry=registry, store=None
    )
    registry.register(health_agent)
    registry.register(TestRunnerAgent())
    registry.register(CodeAnalyzerAgent())
    registry.register(DiagnosticsReporterAgent())

    diagnostics_service = DiagnosticsService(
        health_agent=health_agent,
        test_agent=TestRunnerAgent(),
        code_agent=CodeAnalyzerAgent(),
        reporter_agent=DiagnosticsReporterAgent(),
        db_client=database_client,
    )
    scheduler = DiagnosticsScheduler(
        run_fn=diagnostics_service.run_full_diagnostics,
        interval_seconds=settings.diagnostics_interval_seconds,
    )

    # Sync in-memory registry to PostgreSQL for audit/visibility.
    _sync_registry_to_db(registry, database_client)

    # Seed a default admin key on first boot if configured.
    if settings.default_admin_key:
        auth_service.seed_default_admin(settings.default_admin_key)

    return AppContainer(
        settings=settings,
        llm_client=llm_client,
        model_router=model_router,
        internal_api=internal_api,
        registry=registry,
        orchestrator=orchestrator,
        store=store,
        database_client=database_client,
        auth_service=auth_service,
        metrics_service=metrics_service,
        workflow_executor=workflow_executor,
        diagnostics_service=diagnostics_service,
        scheduler=scheduler,
    )


def _sync_registry_to_db(registry: AgentRegistry, db: PostgreSQLDatabaseClient) -> None:
    if not db.is_configured:
        return
    try:
        db.connect()
        for agent in registry.all():
            db.upsert_agent_registry(
                name=agent.metadata.name,
                description=agent.metadata.description,
                capabilities=list(agent.metadata.capabilities),
                supports_tools=agent.metadata.supports_tools,
                agent_class=type(agent).__name__,
            )
        _logger.info("Agent registry synced to PostgreSQL (%d agents).", len(registry.all()))
    except Exception as exc:
        _logger.warning("Could not sync agent registry to PostgreSQL: %s", exc)
