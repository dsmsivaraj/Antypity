from __future__ import annotations

import logging

import pytest

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import MathAgent
from backend.auth import AuthService
from backend.embeddings_service import EmbeddingService
from backend.log_handler import setup_logging
from backend.metrics import MetricsService
from backend.storage import PostgreSQLExecutionStore


class FakeInternalAPI:
    def __init__(self, registry: AgentRegistry) -> None:
        self.registry = registry

    async def score_agent(self, agent_name: str, task: str, context: dict) -> int:
        agent = self.registry.get(agent_name)
        assert agent is not None
        return agent.can_handle(task, context)

    async def execute_agent(
        self,
        agent_name: str,
        task: str,
        context: dict,
        model_profile: str | None,
    ) -> dict:
        agent = self.registry.get(agent_name)
        assert agent is not None
        result = agent.execute(task, context)
        return {
            "agent_name": agent.name,
            "output": result.output,
            "used_llm": result.used_llm,
            "provider": str(result.metadata.get("provider", "deterministic")),
            "model_profile": model_profile or agent.preferred_model,
        }


@pytest.mark.asyncio
async def test_postgres_persists_execution_metrics_logs_and_registry(postgres_client):
    setup_logging(postgres_client)

    registry = AgentRegistry()
    math = MathAgent(skills=common_skills)
    registry.register(math)
    postgres_client.upsert_agent_registry(
        name=math.metadata.name,
        description=math.metadata.description,
        capabilities=list(math.metadata.capabilities),
        supports_tools=math.metadata.supports_tools,
        agent_class=type(math).__name__,
    )

    store = PostgreSQLExecutionStore(postgres_client)
    metrics = MetricsService(db=postgres_client)
    orchestrator = AgentOrchestrator(
        registry=registry,
        store=store,
        internal_api=FakeInternalAPI(registry),
        metrics=metrics,
    )
    result = await orchestrator.orchestrate("add 40 and 2")

    logging.getLogger("tests.integration").info(
        "integration log for %s",
        result.execution_id,
        extra={"execution_id": result.execution_id, "agent_name": result.agent_name},
    )

    executions = postgres_client.list_executions()
    assert executions[0]["execution_id"] == result.execution_id
    assert "model_profile" in executions[0]
    assert "provider" in executions[0]

    metrics_rows = postgres_client.list_metrics()
    assert metrics_rows[0]["agent_name"] == "math"
    assert metrics_rows[0]["total_executions"] >= 1

    registry_rows = postgres_client.list_agent_registry()
    assert registry_rows[0]["name"] == "math"

    logs = postgres_client.list_logs(execution_id=result.execution_id)
    assert any(log["execution_id"] == result.execution_id for log in logs)


def test_postgres_auth_api_keys(postgres_client):
    service = AuthService(db=postgres_client, config_enabled=True)
    created = service.create_key(name="ci-operator", role="operator")
    principal = service.validate_key(created["key"])
    assert principal is not None
    assert principal["role"] == "operator"


def test_postgres_pgvector_retrieval(postgres_client):
    if not postgres_client.has_pgvector():
        pytest.skip("pgvector is not enabled on this PostgreSQL instance.")

    service = EmbeddingService(database_client=postgres_client)
    if service.model is None:
        pytest.skip("sentence-transformers model is not available in this environment.")

    service.index_document(
        "resume-pgvector-test",
        "summary",
        "Senior backend engineer with Python, FastAPI, PostgreSQL, and vector search experience.",
    )
    results = service.query("python fastapi vector search", top_k=3)
    assert any(item.get("doc_id") == "resume-pgvector-test" for item in results)


def test_postgres_quality_metrics_summary(postgres_client):
    postgres_client.record_response_quality_metric(
        response_type="cover_letter",
        grounding_score=82,
        citation_count=3,
        confidence="high",
        drift_flag=False,
        metadata={"company_name": "Acme AI"},
    )
    summary = postgres_client.get_response_quality_summary()
    assert summary["total_evaluations"] >= 1
    assert summary["avg_grounding_score"] >= 82
    assert summary["avg_citation_count"] >= 3
