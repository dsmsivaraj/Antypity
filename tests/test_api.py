"""Integration-level tests for all API endpoints via TestClient."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestMetaRoutes:
    def test_root(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert "message" in data
        assert "version" in data

    def test_health(self, client: TestClient):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "llm_enabled" in data
        assert "storage_backend" in data
        assert "auth_enabled" in data

    def test_ready(self, client: TestClient):
        resp = client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] in ("ready", "degraded")
        assert "checks" in data


class TestAgentRoutes:
    def test_list_agents(self, client: TestClient):
        resp = client.get("/agents")
        assert resp.status_code == 200
        agents = resp.json()
        assert isinstance(agents, list)
        assert len(agents) == 4
        names = {a["name"] for a in agents}
        assert "generalist" in names
        assert "planner" in names
        assert "reviewer" in names
        assert "math" in names

    def test_agent_has_required_fields(self, client: TestClient):
        resp = client.get("/agents")
        for agent in resp.json():
            assert "name" in agent
            assert "description" in agent
            assert "capabilities" in agent
            assert isinstance(agent["capabilities"], list)


class TestModelRoutes:
    def test_list_models(self, client: TestClient):
        resp = client.get("/models")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert len(data["models"]) >= 1
        assert "id" in data["models"][0]


class TestExecuteRoute:
    def test_execute_math_task(self, client: TestClient):
        resp = client.post(
            "/execute",
            json={"task": "add 10 and 20"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert data["agent_name"] == "math"
        assert "30" in data["output"]
        assert data["used_llm"] is False
        assert "model_profile" in data

    def test_execute_explicit_agent(self, client: TestClient):
        resp = client.post(
            "/execute",
            json={"task": "help me with something", "agent_name": "generalist"},
        )
        assert resp.status_code == 200
        assert resp.json()["agent_name"] == "generalist"

    def test_execute_unknown_agent_returns_400(self, client: TestClient):
        resp = client.post(
            "/execute",
            json={"task": "test task", "agent_name": "does-not-exist"},
        )
        assert resp.status_code == 400

    def test_execute_task_too_short_returns_422(self, client: TestClient):
        resp = client.post("/execute", json={"task": "ab"})
        assert resp.status_code == 422

    def test_execute_task_too_long_returns_422(self, client: TestClient):
        resp = client.post("/execute", json={"task": "x" * 4001})
        assert resp.status_code == 422

    def test_execute_with_context(self, client: TestClient):
        resp = client.post(
            "/execute",
            json={
                "task": "add 5 and 15",
                "context": {"priority": "high"},
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "execution_id" in data
        assert "created_at" in data

    def test_execute_result_stored_in_history(self, client: TestClient):
        client.post("/execute", json={"task": "add 1 and 2"})
        resp = client.get("/executions")
        assert resp.status_code == 200
        assert len(resp.json()["executions"]) >= 1


class TestExecutionHistoryRoute:
    def test_list_executions_empty(self, client: TestClient):
        resp = client.get("/executions")
        assert resp.status_code == 200
        assert "executions" in resp.json()

    def test_list_executions_after_task(self, client: TestClient):
        client.post("/execute", json={"task": "add 3 and 7"})
        resp = client.get("/executions")
        executions = resp.json()["executions"]
        assert len(executions) >= 1
        assert executions[0]["agent_name"] == "math"

    def test_limit_parameter(self, client: TestClient):
        for i in range(5):
            client.post("/execute", json={"task": f"add {i} and {i + 1}"})
        resp = client.get("/executions?limit=3")
        assert resp.status_code == 200
        assert len(resp.json()["executions"]) <= 3


class TestMetricsRoute:
    def test_metrics_endpoint(self, client: TestClient):
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "metrics" in resp.json()


class TestLogsRoute:
    def test_logs_endpoint(self, client: TestClient):
        resp = client.get("/logs")
        assert resp.status_code == 200
        assert "logs" in resp.json()


class TestAuthRoutes:
    def test_auth_disabled_keys_returns_empty(self, client: TestClient):
        # Auth is disabled in test settings — list keys should return empty
        resp = client.get("/auth/keys")
        assert resp.status_code == 200
        assert resp.json()["keys"] == []

    def test_create_key_fails_when_auth_disabled(self, client: TestClient):
        resp = client.post(
            "/auth/keys",
            json={"name": "test-key", "role": "operator"},
        )
        # Returns 503 when auth service is disabled
        assert resp.status_code == 503


class TestWorkflowRoutes:
    def test_list_definitions_no_db(self, client: TestClient):
        resp = client.get("/workflows/definitions")
        assert resp.status_code == 200
        assert resp.json()["definitions"] == []

    def test_create_definition_requires_db(self, client: TestClient):
        resp = client.post(
            "/workflows/definitions",
            json={
                "name": "test-workflow",
                "description": "A test",
                "steps": [{"task_template": "add 1 and 2"}],
            },
        )
        # 503 because no DB is configured in tests
        assert resp.status_code == 503

    def test_list_workflow_executions_no_db(self, client: TestClient):
        resp = client.get("/workflows/executions")
        assert resp.status_code == 200
        assert resp.json()["executions"] == []
