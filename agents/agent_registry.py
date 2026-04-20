from __future__ import annotations

from typing import Dict, List, Optional

from shared.base_agent import AgentMetadata, BaseAgent


class AgentRegistry:
    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        self._agents[agent.name] = agent

    def get(self, name: str) -> Optional[BaseAgent]:
        return self._agents.get(name)

    def list_names(self) -> List[str]:
        return sorted(self._agents.keys())

    def list_metadata(self) -> List[AgentMetadata]:
        return [self._agents[name].metadata for name in self.list_names()]

    def all(self) -> List[BaseAgent]:
        return [self._agents[name] for name in self.list_names()]
