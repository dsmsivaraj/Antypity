from __future__ import annotations

import re
from typing import Dict, Optional

from backend.llm_client import LLMClient
from shared.base_agent import AgentMetadata, AgentResult, BaseAgent, Skill


class GeneralistAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, skills: Optional[list[Skill]] = None):
        super().__init__(
            metadata=AgentMetadata(
                name="generalist",
                description="Handles product, platform, and general execution tasks.",
                capabilities=[
                    "general reasoning",
                    "task decomposition",
                    "platform guidance",
                    "fallback response generation",
                ],
            ),
            skills=skills,
        )
        self.llm_client = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        return 40

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        context_summary = {}
        if context and self.skills:
            context_skill = next((skill for skill in self.skills if skill.name == "summarize_context"), None)
            if context_skill:
                context_summary["context_summary"] = context_skill.run(context)

        prompt = (
            "You are the general execution agent for a production-ready application base.\n"
            f"Task:\n{task}\n\n"
            f"Context:\n{context_summary.get('context_summary', context or 'No context provided.')}"
        )
        llm_result = self.llm_client.complete(
            prompt=prompt,
            system_prompt="Return a concise execution response with implementation-ready guidance.",
        )
        return AgentResult(
            output=llm_result.content,
            used_llm=llm_result.used_llm,
            metadata={"provider": llm_result.provider},
        )


class PlannerAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, skills: Optional[list[Skill]] = None):
        super().__init__(
            metadata=AgentMetadata(
                name="planner",
                description="Breaks larger requests into concrete execution plans and implementation steps.",
                capabilities=[
                    "planning",
                    "task decomposition",
                    "implementation sequencing",
                ],
            ),
            skills=skills,
        )
        self.llm_client = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        if re.search(r"\b(plan|roadmap|break down|decompose|sequence|steps)\b", task.lower()):
            return 92
        return 25

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        prompt = (
            "Create a concise implementation plan with clear ordered steps.\n"
            f"Task:\n{task}\n\n"
            f"Context:\n{context or 'No context provided.'}"
        )
        llm_result = self.llm_client.complete(
            prompt=prompt,
            system_prompt="Return an implementation plan with practical, production-minded steps.",
        )
        return AgentResult(
            output=llm_result.content,
            used_llm=llm_result.used_llm,
            metadata={"provider": llm_result.provider},
        )


class ReviewerAgent(BaseAgent):
    def __init__(self, llm_client: LLMClient, skills: Optional[list[Skill]] = None):
        super().__init__(
            metadata=AgentMetadata(
                name="reviewer",
                description="Reviews code and changesets for bugs, risks, regressions, and production-readiness issues.",
                capabilities=[
                    "code review",
                    "risk identification",
                    "production-readiness review",
                ],
            ),
            skills=skills,
        )
        self.llm_client = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        if re.search(r"\b(review|bug|fix|regression|risk|audit)\b", task.lower()):
            return 88
        return 20

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        prompt = (
            "Review the request as a senior engineer. Focus on bugs, risks, missing validation, "
            "and production readiness.\n"
            f"Task:\n{task}\n\n"
            f"Context:\n{context or 'No context provided.'}"
        )
        llm_result = self.llm_client.complete(
            prompt=prompt,
            system_prompt="Return findings first, then concise remediation guidance.",
        )
        return AgentResult(
            output=llm_result.content,
            used_llm=llm_result.used_llm,
            metadata={"provider": llm_result.provider},
        )


class MathAgent(BaseAgent):
    def __init__(self, skills: Optional[list[Skill]] = None):
        super().__init__(
            metadata=AgentMetadata(
                name="math",
                description="Handles deterministic arithmetic tasks without an LLM dependency.",
                capabilities=["arithmetic", "numeric summarization"],
            ),
            skills=skills,
        )

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        if re.search(r"\b(sum|add|total|calculate|math)\b", task.lower()):
            return 90
        numbers = re.findall(r"-?\d+(?:\.\d+)?", task)
        return 70 if len(numbers) >= 2 else 0

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        values = [float(match) for match in re.findall(r"-?\d+(?:\.\d+)?", task)]
        add_skill = next((skill for skill in self.skills if skill.name == "add_numbers"), None)
        total = add_skill.run(values) if add_skill else sum(values)
        rendered_values = ", ".join(str(value) for value in values) if values else "no numbers"
        return AgentResult(
            output=f"Calculated total: {total} from values [{rendered_values}].",
            used_llm=False,
            metadata={"values": values},
        )
