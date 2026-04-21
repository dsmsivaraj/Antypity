from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from typing import Optional

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.chatbot_agent import ChatStore
from agents.diagnostics_agent import (
    CodeAnalyzerAgent,
    DiagnosticsReporterAgent,
    HealthCheckAgent,
    TestRunnerAgent,
)
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from agents.workflow_engine import WorkflowExecutor
from backend.auth import AuthService
from backend.career_service import CareerService
from backend.config import Settings
from backend.container import AppContainer
from backend.database import PostgreSQLDatabaseClient
from backend.diagnostics import DiagnosticsService
from backend.embeddings_service import EmbeddingService
from backend.figma_client import FigmaClient
from backend.gemini_client import GeminiClient
from backend.internal_api import InternalPlatformAPI
from backend.llama_client import LocalLlamaClient
from backend.llm_client import LLMClient, LLMResult
from backend.local_llm import OllamaClient
from backend.main import create_app
from backend.metrics import MetricsService
from backend.model_router import ModelRouter
from backend.scheduler import DiagnosticsScheduler
from backend.self_healing import InProcessSelfHealingController
from backend.storage import InMemoryExecutionStore


@pytest.fixture()
def test_settings() -> Settings:
    return Settings.for_testing()


@pytest.fixture()
def mock_llm() -> LLMClient:
    client = MagicMock(spec=LLMClient)
    client.enabled = False
    client.client_error = None
    client.complete.return_value = LLMResult(
        content="Mock LLM fallback response.", used_llm=False, provider="mock"
    )
    return client


@pytest.fixture()
def registry(mock_llm: LLMClient, mock_db: MagicMock) -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(GeneralistAgent(llm_client=mock_llm, skills=common_skills))
    reg.register(PlannerAgent(llm_client=mock_llm, skills=common_skills))
    reg.register(ReviewerAgent(llm_client=mock_llm, skills=common_skills))
    reg.register(MathAgent(skills=common_skills))
    reg.register(HealthCheckAgent(db_client=mock_db, llm_client=mock_llm, registry=reg, store=None))
    reg.register(TestRunnerAgent())
    reg.register(CodeAnalyzerAgent())
    reg.register(DiagnosticsReporterAgent())
    return reg


@pytest.fixture()
def store() -> InMemoryExecutionStore:
    return InMemoryExecutionStore()


@pytest.fixture()
def metrics() -> MetricsService:
    return MetricsService(db=None)  # no DB in unit tests


@pytest.fixture()
def mock_auth(test_settings: Settings) -> AuthService:
    mock_db = MagicMock()
    service = AuthService(db=mock_db, config_enabled=False)
    return service


@pytest.fixture()
def mock_db() -> MagicMock:
    db = MagicMock()
    db.is_configured = False
    db.get_status.return_value = MagicMock(connected=False, detail="not configured")
    db.list_metrics.return_value = []
    db.list_logs.return_value = []
    db.list_api_keys.return_value = []
    db.list_workflow_definitions.return_value = []
    db.list_workflow_executions.return_value = []
    return db


@pytest.fixture()
def container(
    test_settings: Settings,
    mock_llm: LLMClient,
    registry: AgentRegistry,
    store: InMemoryExecutionStore,
    metrics: MetricsService,
    mock_auth: AuthService,
    mock_db: MagicMock,
) -> AppContainer:
    model_router = ModelRouter(settings=test_settings, llm_client=mock_llm)
    internal_api = InternalPlatformAPI(test_settings.internal_api_token)
    orchestrator = AgentOrchestrator(
        registry=registry,
        store=store,
        internal_api=internal_api,
        metrics=metrics,
    )
    workflow_executor = WorkflowExecutor(orchestrator=orchestrator)
    health_agent = HealthCheckAgent(db_client=mock_db, llm_client=mock_llm, registry=registry, store=None)
    diag_service = DiagnosticsService(
        health_agent=health_agent,
        test_agent=TestRunnerAgent(),
        code_agent=CodeAnalyzerAgent(),
        reporter_agent=DiagnosticsReporterAgent(),
        db_client=None,
    )
    scheduler = DiagnosticsScheduler(run_fn=diag_service.run_full_diagnostics, interval_seconds=99999)
    mock_ollama = MagicMock(spec=OllamaClient)
    mock_ollama.enabled = False
    mock_ollama._availability_detail = "disabled in tests"
    mock_ollama.base_url = "http://localhost:11434"
    mock_ollama.model = "llama3"
    mock_ollama.list_local_models.return_value = []
    mock_llama = MagicMock(spec=LocalLlamaClient)
    mock_llama.enabled = False
    mock_gemini = MagicMock(spec=GeminiClient)
    mock_gemini.enabled = False
    mock_gemini.model = "gemini-2.0-flash"
    mock_gemini.list_models.return_value = []
    mock_self_healing = MagicMock(spec=InProcessSelfHealingController)
    mock_self_healing.get_status.return_value = {
        "is_running": False, "cycle_count": 0, "last_cycle_at": None, "history": []
    }
    mock_embedding = MagicMock(spec=EmbeddingService)
    mock_embedding.index_document.return_value = None
    mock_embedding.query.return_value = []
    mock_embedding.status.return_value = {
        "backend": "token-index", "model_loaded": False, "pgvector_enabled": False,
        "faiss_enabled": False, "fallback_enabled": True, "document_count": 0,
    }
    career_service = CareerService(
        settings=test_settings,
        model_router=model_router,
        database_client=mock_db,
        embedding_service=mock_embedding,
    )
    return AppContainer(
        settings=test_settings,
        llm_client=mock_llm,
        llama_client=mock_llama,
        model_router=model_router,
        internal_api=internal_api,
        registry=registry,
        orchestrator=orchestrator,
        store=store,
        database_client=mock_db,
        auth_service=mock_auth,
        metrics_service=metrics,
        career_service=career_service,
        workflow_executor=workflow_executor,
        diagnostics_service=diag_service,
        scheduler=scheduler,
        self_healing=mock_self_healing,
        ollama_client=mock_ollama,
        gemini_client=mock_gemini,
        figma_client=FigmaClient(),
        chat_store=ChatStore(),
        embedding_service=mock_embedding,
    )


@pytest.fixture()
def client(container: AppContainer) -> TestClient:
    app = create_app(container=container)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture()
def postgres_dsn() -> Optional[str]:
    return os.getenv("DATABASE_URL")


@pytest.fixture()
def postgres_client(postgres_dsn: Optional[str]):
    if not postgres_dsn:
        pytest.skip("DATABASE_URL not configured for PostgreSQL integration tests.")

    base = Settings.for_testing()
    settings = Settings(
        app_name="Actypity PG Test",
        app_version="0.0.1-test",
        debug=True,
        secret_key="test-secret-key",
        api_host="127.0.0.1",
        api_port=8000,
        cors_origins=["http://localhost:5173"],
        storage_backend="postgres",
        storage_path=base.storage_path,
        auth_enabled=True,
        default_admin_key="act_default_test_admin",
        bootstrap_admin_token="test-bootstrap-token",
        internal_api_token="test-internal-token",
        postgres_dsn=postgres_dsn,
        postgres_host="localhost",
        postgres_port=5432,
        postgres_database="actypity_test",
        postgres_user="postgres",
        postgres_password="postgres",
        postgres_ssl_mode=None,
        postgres_pool_size=2,
        postgres_max_overflow=2,
        postgres_echo=False,
        azure_openai_api_key=None,
        azure_openai_endpoint=None,
        azure_openai_deployment=None,
        azure_openai_planner_deployment=None,
        azure_openai_reviewer_deployment=None,
        azure_openai_api_version="2024-02-01",
        llama_model_path=None,
        llama_resume_model_path=None,
        llama_job_model_path=None,
        llama_template_model_path=None,
        llama_n_ctx=2048,
        llama_temperature=0.2,
        trusted_job_sources=["linkedin", "indeed", "glassdoor"],
        request_timeout_seconds=5.0,
        max_tokens=500,
        diagnostics_interval_seconds=1800,
        ollama_base_url="http://localhost:11434",
        ollama_model="llama3",
        ollama_models_dir=None,
        figma_access_token=None,
        figma_team_id=None,
        figma_file_key=None,
        rapidapi_key=None,
        rapidapi_host="jsearch.p.rapidapi.com",
        linkedin_client_id=None,
        linkedin_client_secret=None,
        indeed_publisher_id=None,
        glassdoor_partner_id=None,
        glassdoor_api_key=None,
        adzuna_app_id=None,
        adzuna_api_key=None,
        google_client_id=None,
        google_client_secret=None,
            gemini_api_key=None,
            gemini_model="gemini-2.0-flash",
            default_model_profile=None,
            retrieval_local_fallback_enabled=True,
            retrieval_candidate_pool_size=12,
        )
    db = PostgreSQLDatabaseClient(settings)
    try:
        db.connect()
    except Exception as exc:
        pytest.skip(f"PostgreSQL integration tests skipped because DATABASE_URL is not reachable: {exc}")
    db.reset_all()
    yield db
    db.reset_all()
