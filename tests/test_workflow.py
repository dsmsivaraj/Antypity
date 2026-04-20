"""Unit tests for WorkflowExecutor."""
from __future__ import annotations

import pytest

from agents.agent_orchestrator import AgentOrchestrator
from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import MathAgent
from agents.workflow_engine import WorkflowExecutor, WorkflowStep
from backend.metrics import MetricsService
from backend.storage import InMemoryExecutionStore
from shared.base_agent import AgentMetadata, AgentResult, BaseAgent


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


class _GreetAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            metadata=AgentMetadata(
                name="greeter",
                description="Says hello.",
                capabilities=["greeting"],
            )
        )

    def can_handle(self, task, context=None) -> int:
        return 60 if "greet" in task.lower() else 0

    def execute(self, task, context=None) -> AgentResult:
        return AgentResult(output="Hello!", used_llm=False, metadata={})


class _EchoAgent(BaseAgent):
    def __init__(self):
        super().__init__(
            metadata=AgentMetadata(
                name="echo",
                description="Echoes the task.",
                capabilities=["echo"],
            )
        )

    def can_handle(self, task, context=None) -> int:
        return 50

    def execute(self, task, context=None) -> AgentResult:
        return AgentResult(output=f"Echo: {task}", used_llm=False, metadata={})


@pytest.fixture()
def registry():
    reg = AgentRegistry()
    reg.register(MathAgent(skills=common_skills))
    reg.register(_GreetAgent())
    reg.register(_EchoAgent())
    return reg


@pytest.fixture()
def executor(registry):
    orchestrator = AgentOrchestrator(
        registry=registry,
        store=InMemoryExecutionStore(),
        internal_api=FakeInternalAPI(registry),
        metrics=MetricsService(db=None),
    )
    return WorkflowExecutor(orchestrator=orchestrator)


class TestWorkflowExecution:
    @pytest.mark.asyncio
    async def test_single_step_completes(self, executor):
        steps = [WorkflowStep(task_template="add 3 and 7")]
        result = await executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"
        assert len(result.steps) == 1
        assert "10" in result.final_output
        assert result.steps[0].execution_id

    @pytest.mark.asyncio
    async def test_multi_step_passes_output_forward(self, executor):
        steps = [
            WorkflowStep(task_template="add 5 and 5"),
            WorkflowStep(task_template="Previous result was: {previous_output}", agent_name="echo"),
        ]
        result = await executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"
        assert "Previous result was:" in result.final_output

    @pytest.mark.asyncio
    async def test_explicit_agent_name_in_step(self, executor):
        steps = [WorkflowStep(task_template="greet the user", agent_name="greeter")]
        result = await executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"
        assert result.steps[0].agent_name == "greeter"
        assert result.steps[0].output == "Hello!"

    @pytest.mark.asyncio
    async def test_unknown_agent_name_fails_workflow(self, executor):
        steps = [WorkflowStep(task_template="do something", agent_name="ghost")]
        result = await executor.execute("wf-1", "exec-1", steps)
        assert result.status == "failed"
        assert result.error is not None

    @pytest.mark.asyncio
    async def test_no_viable_agent_fails_workflow(self, executor):
        empty_registry = AgentRegistry()
        empty_executor = WorkflowExecutor(
            orchestrator=AgentOrchestrator(
                registry=empty_registry,
                store=InMemoryExecutionStore(),
                internal_api=FakeInternalAPI(empty_registry),
                metrics=MetricsService(db=None),
            )
        )
        steps = [WorkflowStep(task_template="something")]
        result = await empty_executor.execute("wf-1", "exec-1", steps)
        assert result.status == "failed"

    @pytest.mark.asyncio
    async def test_step_results_recorded(self, executor):
        steps = [
            WorkflowStep(task_template="add 1 and 2"),
            WorkflowStep(task_template="add 3 and 4"),
        ]
        result = await executor.execute("wf-1", "exec-1", steps)
        assert len(result.steps) == 2
        for step_result in result.steps:
            assert step_result.success is True

    @pytest.mark.asyncio
    async def test_initial_context_available_in_template(self, executor):
        steps = [WorkflowStep(task_template="echo {user}")]
        result = await executor.execute(
            "wf-1", "exec-1", steps, initial_context={"user": "alice"}
        )
        assert result.status == "completed"
        assert "alice" in result.final_output

    @pytest.mark.asyncio
    async def test_step_context_merged_with_global(self, executor):
        steps = [
            WorkflowStep(
                task_template="greet {name}",
                agent_name="echo",
                context={"name": "bob"},
            )
        ]
        result = await executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"

    @pytest.mark.asyncio
    async def test_failed_step_stops_workflow(self):
        class _BoomAgent(BaseAgent):
            def __init__(self):
                super().__init__(
                    metadata=AgentMetadata(name="boom", description="Fails", capabilities=[])
                )

            def can_handle(self, task, context=None):
                return 100

            def execute(self, task, context=None):
                raise RuntimeError("Simulated failure")

        reg = AgentRegistry()
        reg.register(_BoomAgent())
        broken = WorkflowExecutor(
            orchestrator=AgentOrchestrator(
                registry=reg,
                store=InMemoryExecutionStore(),
                internal_api=FakeInternalAPI(reg),
                metrics=MetricsService(db=None),
            )
        )
        steps = [
            WorkflowStep(task_template="first step"),
            WorkflowStep(task_template="second step should not run"),
        ]
        result = await broken.execute("wf-1", "exec-1", steps)
        assert result.status == "failed"
        assert len(result.steps) == 1
