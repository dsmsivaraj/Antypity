from __future__ import annotations

import logging

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import MathAgent
from backend.auth import AuthService
from backend.log_handler import setup_logging
from backend.metrics import MetricsService
from backend.storage import PostgreSQLExecutionStore


def test_postgres_persists_execution_metrics_logs_and_registry(postgres_client):
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
    orchestrator = AgentOrchestrator(registry=registry, store=store, metrics=metrics)
    result = orchestrator.orchestrate("add 40 and 2")

    logging.getLogger("tests.integration").info(
        "integration log for %s",
        result.execution_id,
        extra={"execution_id": result.execution_id, "agent_name": result.agent_name},
    )

    executions = postgres_client.list_executions()
    assert executions[0]["execution_id"] == result.execution_id

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
