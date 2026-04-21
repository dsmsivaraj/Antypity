from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from shared.service_utils.api_client import InternalAPIClient

_logger = logging.getLogger(__name__)


class SelfHealingController:
    """The brain that orchestrates the self-healing loop."""

    def __init__(
        self,
        diagnostics_client: InternalAPIClient,
        repair_client: InternalAPIClient,
        interval_seconds: int = 300,  # 5 minutes
    ) -> None:
        self.diagnostics = diagnostics_client
        self.repair = repair_client
        self.interval = interval_seconds
        self.is_running = False
        self.history: List[Dict[str, Any]] = []

    async def start(self) -> None:
        if self.is_running:
            return
        self.is_running = True
        _logger.info("Self-healing controller loop started (interval=%ds).", self.interval)
        asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self.is_running = False
        _logger.info("Self-healing controller loop stopped.")

    async def _run_loop(self) -> None:
        while self.is_running:
            try:
                await self.run_cycle()
            except Exception as exc:
                _logger.error("Error in self-healing cycle: %s", exc)
            await asyncio.sleep(self.interval)

    async def run_cycle(self) -> Dict[str, Any]:
        """A single monitor-analyze-repair-verify cycle."""
        timestamp = datetime.now(timezone.utc).isoformat()
        _logger.info("Starting self-healing cycle at %s", timestamp)
        
        cycle_record = {
            "timestamp": timestamp,
            "actions": [],
            "status": "started",
        }

        # 1. Monitor & Evaluate
        try:
            report = await self.diagnostics.get("/diagnostics/report")
            issues = report.get("metadata", {}).get("issues", [])
            cycle_record["initial_issues_count"] = len(issues)
            
            if not issues:
                _logger.info("No issues detected. System is healthy.")
                cycle_record["status"] = "healthy"
                self._add_to_history(cycle_record)
                return cycle_record

            # 2. Repair
            for issue in issues:
                action = await self._process_issue(issue)
                if action:
                    cycle_record["actions"].append(action)

            # 3. Verify
            if cycle_record["actions"]:
                _logger.info("Repairs attempted. Re-running diagnostics for verification...")
                final_report = await self.diagnostics.get("/diagnostics/report")
                final_issues = final_report.get("metadata", {}).get("issues", [])
                cycle_record["final_issues_count"] = len(final_issues)
                cycle_record["status"] = "verified" if len(final_issues) < len(issues) else "incomplete"
            else:
                cycle_record["status"] = "no_action_taken"

        except Exception as exc:
            _logger.error("Failed to complete self-healing cycle: %s", exc)
            cycle_record["status"] = "error"
            cycle_record["error"] = str(exc)

        self._add_to_history(cycle_record)
        return cycle_record

    async def _process_issue(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        severity = issue.get("severity")
        category = issue.get("category")
        message = issue.get("message")

        _logger.info("Processing issue: [%s] %s: %s", severity, category, message)

        # Service-level repair
        if category == "health" and "unreachable" in message.lower():
            service_name = "postgresql" if "database" in message.lower() else "backend"
            _logger.info("Attempting service restart for: %s", service_name)
            res = await self.repair.post("/repair/service", json={"service_name": service_name})
            return {"type": "service_restart", "service": service_name, "result": res.get("output")}

        # Code-level repair (for critical/warning quality/test issues)
        if severity in ("critical", "warning") and category in ("quality", "test"):
            _logger.info("Attempting code repair for issue in: %s", issue.get("file"))
            res = await self.repair.post("/repair/code", json={"issue": issue})
            return {"type": "code_repair", "file": issue.get("file"), "result": res.get("output")}

        return None

    def _add_to_history(self, record: Dict[str, Any]) -> None:
        self.history.append(record)
        # Keep last 50 cycles
        if len(self.history) > 50:
            self.history.pop(0)

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval,
            "history": self.history,
            "last_cycle": self.history[-1] if self.history else None,
        }
