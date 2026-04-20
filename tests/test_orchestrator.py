"""Unit tests for AgentOrchestrator API-driven routing and execution."""
from __future__ import annotations

import pytest

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import GeneralistAgent, MathAgent, PlannerAgent, ReviewerAgent
from backend.llm_client import LLMResult
from backend.metrics import MetricsService
from backend.storage import InMemoryExecutionStore


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


@pytest.fixture()
def mock_llm():
    class _MockLLM:
        enabled = False

        @staticmethod
        def complete(prompt, system_prompt=None, deployment=None):  # noqa: ARG004
            return LLMResult(content="Fallback output.", used_llm=False, provider="mock")

    return _MockLLM()


@pytest.fixture()
def orchestrator(mock_llm):
    registry = AgentRegistry()
    registry.register(GeneralistAgent(llm_client=mock_llm, skills=common_skills))
    registry.register(PlannerAgent(llm_client=mock_llm, skills=common_skills))
    registry.register(ReviewerAgent(llm_client=mock_llm, skills=common_skills))
    registry.register(MathAgent(skills=common_skills))
    store = InMemoryExecutionStore()
    metrics = MetricsService(db=None)
    return AgentOrchestrator(
        registry=registry,
        store=store,
        internal_api=FakeInternalAPI(registry),
        metrics=metrics,
    )


class TestScoreBasedRouting:
    @pytest.mark.asyncio
    async def test_math_agent_selected_for_numeric_task(self, orchestrator):
        result = await orchestrator.orchestrate(task="add 10 and 20")
        assert result.agent_name == "math"

    @pytest.mark.asyncio
    async def test_math_agent_selected_for_sum_keyword(self, orchestrator):
        result = await orchestrator.orchestrate(task="sum these numbers: 5 10 15")
        assert result.agent_name == "math"

    @pytest.mark.asyncio
    async def test_generalist_selected_for_general_task(self, orchestrator):
        result = await orchestrator.orchestrate(task="explain the deployment strategy")
        assert result.agent_name == "generalist"

    @pytest.mark.asyncio
    async def test_planner_selected_for_plan_task(self, orchestrator):
        result = await orchestrator.orchestrate(task="plan the rollout steps for the release")
        assert result.agent_name == "planner"

    @pytest.mark.asyncio
    async def test_reviewer_selected_for_review_task(self, orchestrator):
        result = await orchestrator.orchestrate(task="review this fix for bugs and regressions")
        assert result.agent_name == "reviewer"

    @pytest.mark.asyncio
    async def test_explicit_agent_name_overrides_scoring(self, orchestrator):
        result = await orchestrator.orchestrate(task="add 3 and 4", agent_name="generalist")
        assert result.agent_name == "generalist"

    @pytest.mark.asyncio
    async def test_unknown_agent_raises_value_error(self, orchestrator):
        with pytest.raises(ValueError, match="Unknown agent"):
            await orchestrator.orchestrate(task="do something", agent_name="nonexistent")

    @pytest.mark.asyncio
    async def test_empty_registry_raises_value_error(self):
        registry = AgentRegistry()
        store = InMemoryExecutionStore()
        orchestrator = AgentOrchestrator(
            registry=registry,
            store=store,
            internal_api=FakeInternalAPI(registry),
        )
        with pytest.raises(ValueError, match="No agents are registered"):
            await orchestrator.orchestrate(task="some task")


class TestOrchestrationResult:
    @pytest.mark.asyncio
    async def test_result_has_execution_id(self, orchestrator):
        result = await orchestrator.orchestrate(task="add 1 and 2")
        assert result.execution_id
        assert len(result.execution_id) == 36

    @pytest.mark.asyncio
    async def test_result_stored_in_store(self, orchestrator):
        await orchestrator.orchestrate(task="add 5 and 5")
        records = orchestrator.store.list_recent()
        assert len(records) == 1
        assert records[0]["agent_name"] == "math"

    @pytest.mark.asyncio
    async def test_context_passed_through(self, orchestrator):
        context = {"project": "actypity", "priority": "high"}
        result = await orchestrator.orchestrate(task="add 2 and 3", context=context)
        assert result.context == context

    @pytest.mark.asyncio
    async def test_used_llm_false_for_math(self, orchestrator):
        result = await orchestrator.orchestrate(task="total of 7 and 8")
        assert result.used_llm is False

    @pytest.mark.asyncio
    async def test_status_is_completed(self, orchestrator):
        result = await orchestrator.orchestrate(task="add 1 and 1")
        assert result.status == "completed"
