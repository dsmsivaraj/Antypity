from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .agent_orchestrator import AgentOrchestrator

_logger = logging.getLogger(__name__)


@dataclass
class WorkflowStep:
    task_template: str
    agent_name: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepResult:
    step_index: int
    execution_id: Optional[str]
    agent_name: str
    output: str
    used_llm: bool
    success: bool
    error: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        return {
            "step_index": self.step_index,
            "execution_id": self.execution_id,
            "agent_name": self.agent_name,
            "output": self.output,
            "used_llm": self.used_llm,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class WorkflowResult:
    workflow_id: str
    execution_id: str
    status: str
    steps: List[StepResult]
    final_output: str
    error: Optional[str] = None


class WorkflowExecutor:
    def __init__(self, orchestrator: AgentOrchestrator) -> None:
        self.orchestrator = orchestrator

    def execute(
        self,
        workflow_id: str,
        execution_id: str,
        steps: List[WorkflowStep],
        initial_context: Optional[Dict[str, Any]] = None,
    ) -> WorkflowResult:
        context = dict(initial_context or {})
        step_results: List[StepResult] = []
        previous_output = ""

        for i, step in enumerate(steps):
            task = self._render_task(step.task_template, previous_output, i + 1, context)
            try:
                step_context = {**context, **step.context}
                orchestration = self.orchestrator.orchestrate(
                    task=task,
                    agent_name=step.agent_name,
                    context=step_context,
                )
                step_result = StepResult(
                    step_index=i,
                    execution_id=orchestration.execution_id,
                    agent_name=orchestration.agent_name,
                    output=orchestration.output,
                    used_llm=orchestration.used_llm,
                    success=True,
                )
                previous_output = orchestration.output
                _logger.info(
                    "Workflow %s step %d/%d completed via agent '%s' (used_llm=%s).",
                    workflow_id,
                    i + 1,
                    len(steps),
                    orchestration.agent_name,
                    orchestration.used_llm,
                    extra={
                        "execution_id": orchestration.execution_id,
                        "agent_name": orchestration.agent_name,
                    },
                )
            except Exception as exc:
                _logger.error(
                    "Workflow %s execution %s step %d raised: %s",
                    workflow_id,
                    execution_id,
                    i + 1,
                    exc,
                )
                step_result = StepResult(
                    step_index=i,
                    execution_id=None,
                    agent_name=step.agent_name or "auto",
                    output="",
                    used_llm=False,
                    success=False,
                    error=str(exc),
                )
                step_results.append(step_result)
                return WorkflowResult(
                    workflow_id=workflow_id,
                    execution_id=execution_id,
                    status="failed",
                    steps=step_results,
                    final_output=previous_output,
                    error=str(exc),
                )

            step_results.append(step_result)

        return WorkflowResult(
            workflow_id=workflow_id,
            execution_id=execution_id,
            status="completed",
            steps=step_results,
            final_output=previous_output,
        )

    def _render_task(
        self,
        template: str,
        previous_output: str,
        step_number: int,
        context: Dict[str, Any],
    ) -> str:
        safe_ctx = {k: v for k, v in context.items() if isinstance(v, (str, int, float, bool))}
        try:
            return template.format(
                previous_output=previous_output,
                step=step_number,
                **safe_ctx,
            )
        except KeyError:
            return template
