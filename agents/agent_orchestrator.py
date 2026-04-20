from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from backend.internal_api import InternalPlatformAPI
from backend.metrics import MetricsService
from backend.storage import ExecutionStore

from .agent_registry import AgentRegistry

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OrchestrationResult:
    execution_id: str
    agent_name: str
    status: str
    output: str
    used_llm: bool
    model_profile: Optional[str]
    provider: Optional[str]
    created_at: datetime
    context: Dict[str, Any]


class AgentOrchestrator:
    def __init__(
        self,
        registry: AgentRegistry,
        store: ExecutionStore,
        internal_api: InternalPlatformAPI,
        metrics: Optional[MetricsService] = None,
    ) -> None:
        self.registry = registry
        self.store = store
        self.internal_api = internal_api
        self.metrics = metrics

    async def orchestrate(
        self,
        task: str,
        agent_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        model_profile: Optional[str] = None,
    ) -> OrchestrationResult:
        resolved_context = context or {}
        execution_id = str(uuid4())
        resolved_agent_name = await self._resolve_agent(
            task=task,
            agent_name=agent_name,
            context=resolved_context,
        )

        _logger.info(
            "Executing task via agent '%s' (execution_id=%s).",
            resolved_agent_name,
            execution_id,
            extra={"execution_id": execution_id, "agent_name": resolved_agent_name},
        )

        failed = False
        agent_response: Dict[str, Any] = {}
        try:
            agent_response = await self.internal_api.execute_agent(
                resolved_agent_name,
                task=task,
                context=resolved_context,
                model_profile=model_profile,
            )
        except Exception as exc:
            failed = True
            _logger.error(
                "Agent '%s' raised during execution %s: %s",
                resolved_agent_name, execution_id, exc,
                extra={"execution_id": execution_id, "agent_name": resolved_agent_name},
            )
            raise

        finally:
            if self.metrics:
                used_llm = False if failed else bool(agent_response.get("used_llm", False))
                self.metrics.record(agent_name=resolved_agent_name, used_llm=used_llm, failed=failed)

        created_at = datetime.now(timezone.utc)
        result = OrchestrationResult(
            execution_id=execution_id,
            agent_name=resolved_agent_name,
            status="completed",
            output=agent_response["output"],
            used_llm=bool(agent_response["used_llm"]),
            model_profile=agent_response.get("model_profile"),
            provider=agent_response.get("provider"),
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
                "model_profile": result.model_profile,
                "provider": result.provider,
                "created_at": result.created_at.isoformat(),
                "context": result.context,
            }
        )

        _logger.info(
            "Execution %s completed (agent='%s', used_llm=%s).",
            execution_id, resolved_agent_name, result.used_llm,
            extra={"execution_id": execution_id, "agent_name": resolved_agent_name},
        )
        return result

    async def _resolve_agent(
        self,
        task: str,
        agent_name: Optional[str],
        context: Dict[str, Any],
    ) -> str:
        if agent_name:
            agent = self.registry.get(agent_name)
            if agent is None:
                raise ValueError(f"Unknown agent '{agent_name}'.")
            return agent.name

        scored_agents = []
        for agent in self.registry.all():
            score = await self.internal_api.score_agent(agent.name, task=task, context=context)
            scored_agents.append((score, agent.name))
        viable_agents = [(score, agent_name) for score, agent_name in scored_agents if score > 0]
        if not viable_agents:
            raise ValueError("No agents are registered to handle the task.")
        viable_agents.sort(key=lambda item: item[0], reverse=True)
        return viable_agents[0][1]
