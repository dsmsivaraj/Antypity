from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.chatbot_agent import ChatbotAgent, ChatStore
from agents.diagnostics_agent import (
    CodeAnalyzerAgent,
    DiagnosticsReporterAgent,
    HealthCheckAgent,
    TestRunnerAgent,
)
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from agents.llama_resume_agent import LlamaResumeAgent
from agents.job_search_agent import EnhancedJobSearchAgent
from agents.resume_agent import LocalJDAgent, LocalResumeAgent, ResumeTemplateAgent
from agents.workflow_engine import WorkflowExecutor

from .auth import AuthService
from .career_service import CareerService
from .config import Settings, get_settings
from .database import PostgreSQLDatabaseClient
from .diagnostics import DiagnosticsService
from .figma_client import FigmaClient
from .internal_api import InternalPlatformAPI
from .llama_client import LocalLlamaClient
from .llm_client import LLMClient
from .local_llm import OllamaClient
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
    llama_client: LocalLlamaClient
    model_router: ModelRouter
    internal_api: InternalPlatformAPI
    registry: AgentRegistry
    orchestrator: AgentOrchestrator
    store: ExecutionStore
    database_client: PostgreSQLDatabaseClient
    auth_service: AuthService
    metrics_service: MetricsService
    career_service: CareerService
    workflow_executor: WorkflowExecutor
    diagnostics_service: DiagnosticsService
    scheduler: DiagnosticsScheduler
    ollama_client: OllamaClient
    figma_client: FigmaClient
    chat_store: ChatStore


def build_container() -> AppContainer:
    settings = get_settings()

    database_client = PostgreSQLDatabaseClient(settings)
    setup_logging(database_client)

    llm_client = LLMClient(settings)
    llama_client = LocalLlamaClient(settings)
    ollama_client = OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
    )
    figma_client = FigmaClient(
        access_token=settings.figma_access_token,
        team_id=settings.figma_team_id,
        file_key=settings.figma_file_key,
    )
    chat_store = ChatStore()

    model_router = ModelRouter(
        settings=settings,
        llm_client=llm_client,
        llama_client=llama_client if llama_client.enabled else None,
    )
    internal_api = InternalPlatformAPI(internal_token=settings.internal_api_token)
    metrics_service = MetricsService(db=database_client if database_client.is_configured else None)
    auth_service = AuthService(db=database_client, config_enabled=settings.auth_enabled)
    career_service = CareerService(
        settings=settings,
        model_router=model_router,
        database_client=database_client,
    )

    registry = AgentRegistry()
    registry.register(GeneralistAgent(llm_client=llm_client, skills=common_skills))
    registry.register(PlannerAgent(llm_client=llm_client, skills=common_skills))
    registry.register(ReviewerAgent(llm_client=llm_client, skills=common_skills))
    registry.register(MathAgent(skills=common_skills))
    registry.register(LlamaResumeAgent(llm_client=llm_client, skills=common_skills))

    # Local Llama / Ollama-powered agents
    registry.register(LocalResumeAgent(ollama_client=ollama_client))
    registry.register(LocalJDAgent(ollama_client=ollama_client))
    registry.register(ResumeTemplateAgent(figma_client=figma_client, ollama_client=ollama_client))
    registry.register(ChatbotAgent(
        ollama_client=ollama_client,
        llm_client=llm_client,
        chat_store=chat_store,
    ))
    registry.register(EnhancedJobSearchAgent(ollama_client=ollama_client))

    store = build_execution_store(settings, database_client=database_client)
    orchestrator = AgentOrchestrator(
        registry=registry,
        store=store,
        internal_api=internal_api,
        metrics=metrics_service,
    )
    workflow_executor = WorkflowExecutor(orchestrator=orchestrator)

    # Diagnostic agents
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

    _sync_registry_to_db(registry, database_client)

    if settings.default_admin_key:
        auth_service.seed_default_admin(settings.default_admin_key)

    _logger.info(
        "Container built: ollama=%s llama=%s figma=%s",
        ollama_client.enabled,
        llama_client.enabled,
        figma_client.enabled,
    )

    return AppContainer(
        settings=settings,
        llm_client=llm_client,
        llama_client=llama_client,
        model_router=model_router,
        internal_api=internal_api,
        registry=registry,
        orchestrator=orchestrator,
        store=store,
        database_client=database_client,
        auth_service=auth_service,
        metrics_service=metrics_service,
        career_service=career_service,
        workflow_executor=workflow_executor,
        diagnostics_service=diagnostics_service,
        scheduler=scheduler,
        ollama_client=ollama_client,
        figma_client=figma_client,
        chat_store=chat_store,
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
