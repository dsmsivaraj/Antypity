"""Unit tests for WorkflowExecutor."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agents.agent_registry import AgentRegistry
from agents.agent_skills import common_skills
from agents.example_agent import MathAgent
from agents.agent_orchestrator import AgentOrchestrator
from backend.metrics import MetricsService
from backend.storage import InMemoryExecutionStore
from agents.workflow_engine import WorkflowExecutor, WorkflowStep
from shared.base_agent import AgentMetadata, AgentResult, BaseAgent


class _GreetAgent(BaseAgent):
    """Deterministic test agent that greets."""

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
    """Echoes the task back — useful for testing template substitution."""

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
        metrics=MetricsService(db=None),
    )
    return WorkflowExecutor(orchestrator=orchestrator)


class TestWorkflowExecution:
    def test_single_step_completes(self, executor):
        steps = [WorkflowStep(task_template="add 3 and 7")]
        result = executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"
        assert len(result.steps) == 1
        assert "10" in result.final_output
        assert result.steps[0].execution_id

    def test_multi_step_passes_output_forward(self, executor):
        steps = [
            WorkflowStep(task_template="add 5 and 5"),
            # Explicitly use echo agent so numbers in previous_output don't cause math agent to win
            WorkflowStep(task_template="Previous result was: {previous_output}", agent_name="echo"),
        ]
        result = executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"
        assert "Previous result was:" in result.final_output

    def test_explicit_agent_name_in_step(self, executor):
        steps = [WorkflowStep(task_template="greet the user", agent_name="greeter")]
        result = executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"
        assert result.steps[0].agent_name == "greeter"
        assert result.steps[0].output == "Hello!"

    def test_unknown_agent_name_fails_workflow(self, executor):
        steps = [WorkflowStep(task_template="do something", agent_name="ghost")]
        result = executor.execute("wf-1", "exec-1", steps)
        assert result.status == "failed"
        assert result.error is not None

    def test_no_viable_agent_fails_workflow(self, executor):
        empty_registry = AgentRegistry()
        empty_executor = WorkflowExecutor(
            orchestrator=AgentOrchestrator(
                registry=empty_registry,
                store=InMemoryExecutionStore(),
                metrics=MetricsService(db=None),
            )
        )
        steps = [WorkflowStep(task_template="something")]
        result = empty_executor.execute("wf-1", "exec-1", steps)
        assert result.status == "failed"

    def test_step_results_recorded(self, executor):
        steps = [
            WorkflowStep(task_template="add 1 and 2"),
            WorkflowStep(task_template="add 3 and 4"),
        ]
        result = executor.execute("wf-1", "exec-1", steps)
        assert len(result.steps) == 2
        for step_result in result.steps:
            assert step_result.success is True

    def test_initial_context_available_in_template(self, executor):
        steps = [WorkflowStep(task_template="echo {user}")]
        result = executor.execute(
            "wf-1", "exec-1", steps, initial_context={"user": "alice"}
        )
        assert result.status == "completed"
        assert "alice" in result.final_output

    def test_step_context_merged_with_global(self, executor):
        steps = [
            WorkflowStep(
                task_template="greet {name}",
                agent_name="echo",
                context={"name": "bob"},
            )
        ]
        result = executor.execute("wf-1", "exec-1", steps)
        assert result.status == "completed"

    def test_failed_step_stops_workflow(self, executor):
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
                metrics=MetricsService(db=None),
            )
        )
        steps = [
            WorkflowStep(task_template="first step"),
            WorkflowStep(task_template="second step should not run"),
        ]
        result = broken.execute("wf-1", "exec-1", steps)
        assert result.status == "failed"
        assert len(result.steps) == 1  # stopped after first failure
