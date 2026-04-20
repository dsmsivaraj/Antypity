"""Tests for the self-monitoring diagnostic system."""
from __future__ import annotations

import subprocess
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from agents.diagnostics_agent import (
    CodeAnalyzerAgent,
    DiagnosticsReporterAgent,
    HealthCheckAgent,
    TestRunnerAgent,
)
from backend.diagnostics import DiagnosticsService


# ── HealthCheckAgent ──────────────────────────────────────────────────────────

class TestHealthCheckAgent:
    def _make_agent(self, db_connected=True, llm_enabled=False, agent_count=4):
        db = MagicMock()
        db.is_configured = True
        db.get_status.return_value = MagicMock(
            connected=db_connected,
            detail="ok" if db_connected else "connection refused",
        )

        llm = MagicMock()
        llm.enabled = llm_enabled
        llm.client_error = None

        registry = MagicMock()
        registry.all.return_value = [MagicMock()] * agent_count

        return HealthCheckAgent(db_client=db, llm_client=llm, registry=registry, store=None)

    def test_scores_high_for_health_keywords(self):
        agent = self._make_agent()
        assert agent.can_handle("run health check") == 90
        assert agent.can_handle("check liveness") == 90
        assert agent.can_handle("monitor platform") == 90

    def test_scores_low_for_unrelated_tasks(self):
        agent = self._make_agent()
        assert agent.can_handle("add 3 and 7") < 10

    def test_reports_ok_when_all_healthy(self):
        agent = self._make_agent(db_connected=True, llm_enabled=True, agent_count=4)
        result = agent.execute("run health check")
        assert result.used_llm is False
        assert "ok" in result.output
        issues = result.metadata["issues"]
        critical = [i for i in issues if i["severity"] == "critical"]
        assert len(critical) == 0

    def test_reports_critical_when_db_down(self):
        agent = self._make_agent(db_connected=False)
        result = agent.execute("run health check")
        issues = result.metadata["issues"]
        assert any(i["severity"] == "critical" and "unreachable" in i["message"] for i in issues)

    def test_reports_critical_when_no_agents(self):
        agent = self._make_agent(agent_count=0)
        result = agent.execute("run health check")
        issues = result.metadata["issues"]
        assert any(i["severity"] == "critical" and "No agents" in i["message"] for i in issues)

    def test_metadata_contains_health_dict(self):
        agent = self._make_agent()
        result = agent.execute("run health check")
        assert "health" in result.metadata
        assert "database" in result.metadata["health"]
        assert "registry" in result.metadata["health"]
        assert "llm" in result.metadata["health"]


# ── TestRunnerAgent ───────────────────────────────────────────────────────────

class TestTestRunnerAgent:
    def test_scores_high_for_test_keywords(self):
        agent = TestRunnerAgent()
        assert agent.can_handle("run tests") == 90
        assert agent.can_handle("run the pytest suite") == 90
        assert agent.can_handle("test coverage report") == 90

    def test_scores_low_for_unrelated_tasks(self):
        agent = TestRunnerAgent()
        assert agent.can_handle("plan the release") < 10

    def test_executes_and_returns_test_results(self):
        agent = TestRunnerAgent()
        result = agent.execute("run test suite")
        assert result.used_llm is False
        assert "tests" in result.metadata
        tests = result.metadata["tests"]
        assert "passed" in tests
        assert "failed" in tests
        assert "status" in tests
        assert tests["status"] in ("PASS", "FAIL", "TIMEOUT", "ERROR", "SKIP")

    def test_pass_when_suite_passes(self):
        fake_output = "99 passed, 0 failed in 12.3s"
        fake_proc = SimpleNamespace(stdout=fake_output, stderr="", returncode=0)
        with patch("subprocess.run", return_value=fake_proc):
            agent = TestRunnerAgent()
            result = agent.execute("run test suite")
        tests = result.metadata["tests"]
        assert tests["passed"] > 0
        assert tests["status"] == "PASS"


# ── CodeAnalyzerAgent ─────────────────────────────────────────────────────────

class TestCodeAnalyzerAgent:
    def test_scores_high_for_analysis_keywords(self):
        agent = CodeAnalyzerAgent()
        assert agent.can_handle("analyze code for issues") == 90
        assert agent.can_handle("static analysis scan") == 90
        assert agent.can_handle("find code gaps") == 90

    def test_executes_without_crash(self):
        agent = CodeAnalyzerAgent()
        result = agent.execute("analyze code")
        assert result.used_llm is False
        assert "files_scanned" in result.metadata
        assert result.metadata["files_scanned"] > 0

    def test_returns_issues_list(self):
        agent = CodeAnalyzerAgent()
        result = agent.execute("analyze code")
        assert "issues" in result.metadata
        assert isinstance(result.metadata["issues"], list)

    def test_issues_have_required_fields(self):
        agent = CodeAnalyzerAgent()
        result = agent.execute("analyze code")
        for issue in result.metadata["issues"]:
            assert "severity" in issue
            assert "category" in issue
            assert "message" in issue
            assert issue["severity"] in ("critical", "warning", "info")

    def test_detects_g4_azure_identity_gap(self):
        agent = CodeAnalyzerAgent()
        result = agent.execute("analyze code")
        issues = result.metadata["issues"]
        messages = [i["message"] for i in issues]
        assert any("azure-identity" in m for m in messages)


# ── DiagnosticsReporterAgent ──────────────────────────────────────────────────

class TestDiagnosticsReporterAgent:
    def test_scores_high_for_report_keywords(self):
        agent = DiagnosticsReporterAgent()
        assert agent.can_handle("generate diagnostic report") == 90
        assert agent.can_handle("full diagnostics") == 90

    def test_reports_healthy_when_no_issues(self):
        agent = DiagnosticsReporterAgent()
        result = agent.execute(
            "generate report",
            context={
                "health": {"database": "ok", "llm": "configured", "registry": "ok (4)", "storage": "ok"},
                "tests": {"passed": 99, "failed": 0, "errors": 0},
                "issues": [],
            },
        )
        assert result.metadata["status"] == "healthy"

    def test_reports_failing_when_critical_issues(self):
        agent = DiagnosticsReporterAgent()
        result = agent.execute(
            "generate report",
            context={
                "health": {},
                "tests": {"passed": 0, "failed": 5, "errors": 0},
                "issues": [{"severity": "critical", "category": "test", "message": "5 failures"}],
            },
        )
        assert result.metadata["status"] == "failing"

    def test_reports_degraded_when_warnings_only(self):
        agent = DiagnosticsReporterAgent()
        result = agent.execute(
            "generate report",
            context={
                "health": {},
                "tests": {"passed": 99, "failed": 0, "errors": 0},
                "issues": [{"severity": "warning", "category": "gap", "message": "placeholder in k8s"}],
            },
        )
        assert result.metadata["status"] == "degraded"


# ── DiagnosticsService ────────────────────────────────────────────────────────

class TestDiagnosticsService:
    def _make_service(self):
        db = MagicMock()
        db.is_configured = False
        llm = MagicMock()
        llm.enabled = False
        llm.client_error = None
        registry = MagicMock()
        registry.all.return_value = [MagicMock()] * 8
        health_agent = HealthCheckAgent(db_client=db, llm_client=llm, registry=registry, store=None)
        return DiagnosticsService(
            health_agent=health_agent,
            test_agent=TestRunnerAgent(),
            code_agent=CodeAnalyzerAgent(),
            reporter_agent=DiagnosticsReporterAgent(),
            db_client=None,
        )

    @pytest.mark.asyncio
    async def test_run_returns_structured_record(self):
        service = self._make_service()
        record = await service.run_full_diagnostics()
        assert "id" in record
        assert "status" in record
        assert "issues" in record
        assert "summary" in record
        assert "created_at" in record
        assert "completed_at" in record
        assert record["status"] in ("healthy", "degraded", "failing")

    @pytest.mark.asyncio
    async def test_run_includes_test_results(self):
        fake_output = "42 passed, 0 failed in 5.1s"
        fake_proc = SimpleNamespace(stdout=fake_output, stderr="", returncode=0)
        with patch("subprocess.run", return_value=fake_proc):
            service = self._make_service()
            record = await service.run_full_diagnostics()
        assert "tests" in record
        assert record["tests"]["passed"] > 0

    def test_get_reports_returns_empty_without_db(self):
        service = self._make_service()
        reports = service.get_reports()
        assert reports == []

    def test_get_latest_returns_none_without_db(self):
        service = self._make_service()
        assert service.get_latest_report() is None


# ── Diagnostics API routes ────────────────────────────────────────────────────

class TestDiagnosticsRoutes:
    def test_run_diagnostics_returns_200(self, client: TestClient):
        resp = client.post("/diagnostics/run")
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["status"] in ("healthy", "degraded", "failing")
        assert "issues" in data
        assert "summary" in data

    def test_list_reports_returns_empty_without_db(self, client: TestClient):
        resp = client.get("/diagnostics/reports")
        assert resp.status_code == 200
        assert resp.json()["runs"] == []

    def test_latest_report_404_when_no_runs(self, client: TestClient):
        resp = client.get("/diagnostics/reports/latest")
        assert resp.status_code == 404

    def test_run_result_has_test_data(self, client: TestClient):
        resp = client.post("/diagnostics/run")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tests"] is not None
        assert "passed" in data["tests"]
        assert "failed" in data["tests"]

    def test_run_result_has_issues_list(self, client: TestClient):
        resp = client.post("/diagnostics/run")
        assert resp.status_code == 200
        issues = resp.json()["issues"]
        assert isinstance(issues, list)
        for issue in issues:
            assert "severity" in issue
            assert "message" in issue
