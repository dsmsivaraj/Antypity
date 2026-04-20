"""Unit tests for AgentOrchestrator score-based routing and execution."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from backend.llm_client import LLMResult
from backend.metrics import MetricsService
from backend.storage import InMemoryExecutionStore


@pytest.fixture()
def mock_llm():
    client = MagicMock()
    client.enabled = False
    client.complete.return_value = LLMResult(
        content="Fallback output.", used_llm=False, provider="mock"
    )
    return client


@pytest.fixture()
def orchestrator(mock_llm):
    registry = AgentRegistry()
    registry.register(GeneralistAgent(llm_client=mock_llm, skills=common_skills))
    registry.register(PlannerAgent(llm_client=mock_llm, skills=common_skills))
    registry.register(ReviewerAgent(llm_client=mock_llm, skills=common_skills))
    registry.register(MathAgent(skills=common_skills))
    store = InMemoryExecutionStore()
    metrics = MetricsService(db=None)
    return AgentOrchestrator(registry=registry, store=store, metrics=metrics)


class TestScoreBasedRouting:
    def test_math_agent_selected_for_numeric_task(self, orchestrator):
        result = orchestrator.orchestrate(task="add 10 and 20")
        assert result.agent_name == "math"

    def test_math_agent_selected_for_sum_keyword(self, orchestrator):
        result = orchestrator.orchestrate(task="sum these numbers: 5 10 15")
        assert result.agent_name == "math"

    def test_generalist_selected_for_general_task(self, orchestrator):
        result = orchestrator.orchestrate(task="explain the deployment strategy")
        assert result.agent_name == "generalist"

    def test_planner_selected_for_plan_task(self, orchestrator):
        result = orchestrator.orchestrate(task="plan the rollout steps for the release")
        assert result.agent_name == "planner"

    def test_reviewer_selected_for_review_task(self, orchestrator):
        result = orchestrator.orchestrate(task="review this fix for bugs and regressions")
        assert result.agent_name == "reviewer"

    def test_explicit_agent_name_overrides_scoring(self, orchestrator):
        result = orchestrator.orchestrate(task="add 3 and 4", agent_name="generalist")
        assert result.agent_name == "generalist"

    def test_unknown_agent_raises_value_error(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown agent"):
            orchestrator.orchestrate(task="do something", agent_name="nonexistent")

    def test_empty_registry_raises_value_error(self):
        registry = AgentRegistry()
        store = InMemoryExecutionStore()
        orchestrator = AgentOrchestrator(registry=registry, store=store)
        with pytest.raises(ValueError, match="No agents are registered"):
            orchestrator.orchestrate(task="some task")


class TestOrchestrationResult:
    def test_result_has_execution_id(self, orchestrator):
        result = orchestrator.orchestrate(task="add 1 and 2")
        assert result.execution_id
        assert len(result.execution_id) == 36  # UUID format

    def test_result_stored_in_store(self, orchestrator):
        orchestrator.orchestrate(task="add 5 and 5")
        records = orchestrator.store.list_recent()
        assert len(records) == 1
        assert records[0]["agent_name"] == "math"

    def test_context_passed_through(self, orchestrator):
        context = {"project": "actypity", "priority": "high"}
        result = orchestrator.orchestrate(task="add 2 and 3", context=context)
        assert result.context == context

    def test_used_llm_false_for_math(self, orchestrator):
        result = orchestrator.orchestrate(task="total of 7 and 8")
        assert result.used_llm is False

    def test_status_is_completed(self, orchestrator):
        result = orchestrator.orchestrate(task="add 1 and 1")
        assert result.status == "completed"


class TestMetricsRecording:
    def test_metric_recorded_after_execution(self, orchestrator):
        orchestrator.metrics = MagicMock(spec=MetricsService)
        orchestrator.orchestrate(task="add 3 and 3")
        orchestrator.metrics.record.assert_called_once_with(
            agent_name="math", used_llm=False, failed=False
        )

    def test_no_error_when_metrics_is_none(self, orchestrator):
        orchestrator.metrics = None
        result = orchestrator.orchestrate(task="add 1 and 2")
        assert result.status == "completed"
