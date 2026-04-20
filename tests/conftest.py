from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from typing import Optional

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from agents.workflow_engine import WorkflowExecutor
from backend.auth import AuthService
from backend.config import Settings
from backend.container import AppContainer
from backend.database import PostgreSQLDatabaseClient
from backend.internal_api import InternalPlatformAPI
from backend.llm_client import LLMClient, LLMResult
from backend.main import create_app
from backend.metrics import MetricsService
from backend.model_router import ModelRouter
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
def registry(mock_llm: LLMClient) -> AgentRegistry:
    reg = AgentRegistry()
    reg.register(GeneralistAgent(llm_client=mock_llm, skills=common_skills))
    reg.register(PlannerAgent(llm_client=mock_llm, skills=common_skills))
    reg.register(ReviewerAgent(llm_client=mock_llm, skills=common_skills))
    reg.register(MathAgent(skills=common_skills))
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
    return AppContainer(
        settings=test_settings,
        llm_client=mock_llm,
        model_router=model_router,
        internal_api=internal_api,
        registry=registry,
        orchestrator=orchestrator,
        store=store,
        database_client=mock_db,
        auth_service=mock_auth,
        metrics_service=metrics,
        workflow_executor=workflow_executor,
    )


@pytest.fixture()
def client(container: AppContainer) -> TestClient:
    app = create_app(container=container)
    return TestClient(app)


@pytest.fixture()
def postgres_dsn() -> Optional[str]:
    return os.getenv("DATABASE_URL")


@pytest.fixture()
def postgres_client(postgres_dsn: Optional[str]):
    if not postgres_dsn:
        pytest.skip("DATABASE_URL not configured for PostgreSQL integration tests.")

    settings = Settings(
        app_name="Actypity PG Test",
        app_version="0.0.1-test",
        debug=True,
        secret_key="test-secret-key",
        api_host="127.0.0.1",
        api_port=8000,
        cors_origins=["http://localhost:5173"],
        storage_backend="postgres",
        storage_path=Settings.for_testing().storage_path,
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
        request_timeout_seconds=5.0,
        max_tokens=500,
    )
    db = PostgreSQLDatabaseClient(settings)
    db.connect()
    db.reset_all()
    yield db
    db.reset_all()
