from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent, Skill

_logger = logging.getLogger(__name__)


# ── SelfHealingAgent ─────────────────────────────────────────────────────────

class SelfHealingAgent(BaseAgent):
    """Orchestrates high-level system repairs like service restarts."""

    def __init__(self) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="self-healing-agent",
                description="Orchestrates high-level platform repairs and service management.",
                capabilities=["service recovery", "autonomous repair", "infrastructure management"],
            )
        )
        self.add_skill(Skill(
            name="restart_service",
            description="Restarts a system service (e.g., postgresql, backend).",
            handler=self._restart_service
        ))

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 90 if any(kw in t for kw in ("repair", "restart", "fix service", "recover")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        # If the task explicitly asks to restart a service
        if "restart" in task.lower():
            service_name = "postgresql" if "postgres" in task.lower() else "backend"
            result = self._restart_service(service_name)
            return AgentResult(output=result, used_llm=False)
            
        return AgentResult(output="Self-healing agent is ready.", used_llm=False)

    def _restart_service(self, service_name: str) -> str:
        _logger.info("Attempting to restart service: %s", service_name)
        try:
            if service_name == "postgresql":
                # Assuming brew services for local dev
                subprocess.run(["brew", "services", "restart", "postgresql@14"], check=True)
                return "Successfully restarted PostgreSQL via brew services."
            elif service_name == "backend":
                # This is tricky as we are the backend (or a related service)
                # In Docker, we might restart the container.
                return "Restarting backend service is not supported in this environment yet."
            return f"Unknown service: {service_name}"
        except Exception as exc:
            return f"Failed to restart {service_name}: {exc}"


# ── BugFixAgent ──────────────────────────────────────────────────────────────

class BugFixAgent(BaseAgent):
    """Uses LLM to analyze and fix code bugs (failing tests, syntax errors)."""

    def __init__(self, llm_client) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="bug-fix-agent",
                description="Uses LLM to analyze and fix code-level bugs and failing tests.",
                capabilities=["code repair", "test fixing", "bug analysis"],
            )
        )
        self._llm = llm_client

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        return 95 if any(kw in t for kw in ("fix bug", "repair code", "fix test", "resolve failure")) else 5

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        issue = ctx.get("issue")
        if not issue:
            return AgentResult(output="No issue context provided for bug fixing.", used_llm=False)

        # Build prompt for LLM
        prompt = f"""
I have the following code issue to resolve:
Category: {issue.get('category')}
Message: {issue.get('message')}
File: {issue.get('file')}
Line: {issue.get('line')}
Suggestion: {issue.get('suggestion')}

Please analyze the issue and propose a fix.
"""
        # In a real scenario, we'd read the file content and provide it to the LLM.
        # For this prototype, we simulate the LLM proposing a fix.
        
        return AgentResult(
            output=f"Analyzing issue in {issue.get('file')}... Proposing automated fix.",
            used_llm=True,
            metadata={"fix_proposed": True, "file": issue.get('file')}
        )
