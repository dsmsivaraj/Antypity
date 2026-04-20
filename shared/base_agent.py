from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass(frozen=True)
class Skill:
    name: str
    description: str
    handler: Callable[..., Any]

    def run(self, *args, **kwargs):
        return self.handler(*args, **kwargs)


@dataclass(frozen=True)
class AgentMetadata:
    name: str
    description: str
    capabilities: List[str]
    supports_tools: bool = False
    preferred_model: Optional[str] = None


@dataclass(frozen=True)
class AgentResult:
    output: str
    used_llm: bool
    metadata: Dict[str, Any]


class BaseAgent(ABC):
    def __init__(self, metadata: AgentMetadata, skills: Optional[List[Skill]] = None):
        self.metadata = metadata
        self.skills = skills or []

    @property
    def name(self) -> str:
        return self.metadata.name

    def add_skill(self, skill: Skill) -> None:
        self.skills.append(skill)

    @property
    def preferred_model(self) -> Optional[str]:
        return self.metadata.preferred_model

    def build_prompt(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, str]]:
        return None

    @abstractmethod
    def can_handle(self, task: str, context: Optional[Dict[str, Any]] = None) -> int:
        raise NotImplementedError

    @abstractmethod
    def execute(self, task: str, context: Optional[Dict[str, Any]] = None) -> AgentResult:
        raise NotImplementedError
