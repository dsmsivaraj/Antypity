from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.metrics import MetricsService
from backend.storage import ExecutionStore
from shared.base_agent import AgentResult

from .agent_registry import AgentRegistry

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestrationResult:
    execution_id: str
    agent_name: str
    status: str
    output: str
    used_llm: bool
    created_at: datetime
    context: Dict[str, Any]


class AgentOrchestrator:
    def __init__(
        self,
        registry: AgentRegistry,
        store: ExecutionStore,
        metrics: Optional[MetricsService] = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.metrics = metrics

    def orchestrate(
        self,
        task: str,
        agent_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestrationResult:
        resolved_context = context or {}
        execution_id = str(uuid4())
        agent = self._resolve_agent(task=task, agent_name=agent_name, context=resolved_context)

        _logger.info(
            "Executing task via agent '%s' (execution_id=%s).",
            agent.name,
            execution_id,
            extra={"execution_id": execution_id, "agent_name": agent.name},
        )

        failed = False
        agent_result: AgentResult
        try:
            agent_result = agent.execute(task, resolved_context)
        except Exception as exc:
            failed = True
            _logger.error(
                "Agent '%s' raised during execution %s: %s",
                agent.name, execution_id, exc,
                extra={"execution_id": execution_id, "agent_name": agent.name},
            )
            raise

        finally:
            if self.metrics:
                used_llm = False if failed else getattr(agent_result, "used_llm", False)
                self.metrics.record(agent_name=agent.name, used_llm=used_llm, failed=failed)

        created_at = datetime.now(timezone.utc)
        result = OrchestrationResult(
            execution_id=execution_id,
            agent_name=agent.name,
            status="completed",
            output=agent_result.output,
            used_llm=agent_result.used_llm,
            created_at=created_at,
            context=resolved_context,
        )

        self.store.save(
            {
                "execution_id": result.execution_id,
                "agent_name": result.agent_name,
                "status": result.status,
                "output": result.output,
                "used_llm": result.used_llm,
                "created_at": result.created_at.isoformat(),
                "context": result.context,
            }
        )

        _logger.info(
            "Execution %s completed (agent='%s', used_llm=%s).",
            execution_id, agent.name, agent_result.used_llm,
            extra={"execution_id": execution_id, "agent_name": agent.name},
        )
        return result

    def _resolve_agent(
        self,
        task: str,
        agent_name: Optional[str],
        context: Dict[str, Any],
    ):
        if agent_name:
            agent = self.registry.get(agent_name)
            if agent is None:
                raise ValueError(f"Unknown agent '{agent_name}'.")
            return agent

        scored_agents = [
            (agent.can_handle(task, context), agent)
            for agent in self.registry.all()
        ]
        viable_agents = [(score, agent) for score, agent in scored_agents if score > 0]
        if not viable_agents:
            raise ValueError("No agents are registered to handle the task.")
        viable_agents.sort(key=lambda item: item[0], reverse=True)
        return viable_agents[0][1]
