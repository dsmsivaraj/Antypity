"""InProcessSelfHealingController — self-healing loop that runs inside the main FastAPI app.

Replaces the external orchestrator-service proxy.  Uses DiagnosticsService directly.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


class InProcessSelfHealingController:
    def __init__(
        self,
        diagnostics_service,
        database_client=None,
        interval_seconds: int = 300,
    ) -> None:
        self._diag = diagnostics_service
        self._db = database_client
        self.interval_seconds = interval_seconds
        self.is_running = False
        self.history: List[Dict[str, Any]] = []
        self._task: Optional[asyncio.Task] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._task is None or self._task.done():
            self.is_running = True
            self._task = asyncio.create_task(self._loop())
            _logger.info("SelfHealingController started (interval=%ds).", self.interval_seconds)

    async def stop(self) -> None:
        self.is_running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        _logger.info("SelfHealingController stopped.")

    # ── Loop ──────────────────────────────────────────────────────────────────

    async def _loop(self) -> None:
        # Run first cycle immediately, then on interval
        await asyncio.sleep(10)
        try:
            while self.is_running:
                try:
                    await self.run_cycle()
                except Exception as exc:
                    _logger.error("Self-healing cycle error: %s", exc)
                await asyncio.sleep(self.interval_seconds)
        except asyncio.CancelledError:
            pass

    # ── Single cycle ─────────────────────────────────────────────────────────

    async def run_cycle(self) -> Dict[str, Any]:
        timestamp = datetime.now(timezone.utc).isoformat()
        _logger.info("Self-healing cycle started at %s", timestamp)

        record: Dict[str, Any] = {
            "timestamp": timestamp,
            "status": "started",
            "actions": [],
        }

        try:
            report = await self._diag.run_full_diagnostics()
            issues = report.get("issues", [])
            record["initial_issues_count"] = len(issues)

            if not issues:
                record["status"] = "healthy"
                _logger.info("Self-healing: system healthy, no issues.")
                self._append(record)
                return record

            _logger.info("Self-healing: found %d issues, attempting repairs.", len(issues))
            for issue in issues:
                action = self._repair_issue(issue)
                if action:
                    record["actions"].append(action)

            # Re-verify only if repairs were applied
            if record["actions"]:
                verify_report = await self._diag.run_full_diagnostics()
                final_issues = verify_report.get("issues", [])
                record["final_issues_count"] = len(final_issues)
                record["status"] = (
                    "repaired" if len(final_issues) < len(issues) else "incomplete"
                )
                _logger.info(
                    "Self-healing: after repairs issues %d→%d (status=%s)",
                    len(issues), len(final_issues), record["status"],
                )
            else:
                record["status"] = "monitored"

        except Exception as exc:
            _logger.error("Self-healing cycle failed: %s", exc)
            record["status"] = "error"
            record["error"] = str(exc)

        self._append(record)
        return record

    # ── Repair actions ────────────────────────────────────────────────────────

    def _repair_issue(self, issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        severity = issue.get("severity", "")
        category = issue.get("category", "")
        message = (issue.get("message") or "").lower()

        # DB connectivity — attempt reconnect
        if category == "health" and ("database" in message or "postgres" in message):
            if self._db and hasattr(self._db, "reconnect"):
                try:
                    self._db.reconnect()
                    return {"type": "db_reconnect", "result": "reconnected successfully"}
                except Exception as exc:
                    return {"type": "db_reconnect", "result": f"reconnect failed: {exc}"}
            return {"type": "db_reconnect", "result": "reconnect not available — check DATABASE_URL"}

        # Service unreachable — log advisory only
        if category == "health" and "unreachable" in message:
            service = issue.get("file") or "unknown"
            _logger.warning("Self-healing advisory: service unreachable — %s", service)
            return {"type": "advisory", "service": service, "result": "logged for operator review"}

        # Code / test critical issues — log
        if severity == "critical":
            _logger.warning(
                "Self-healing: critical issue in %s — %s", issue.get("file", "?"), issue.get("message")
            )
            return {
                "type": "logged",
                "file": issue.get("file"),
                "result": f"critical issue logged: {issue.get('message', '')[:120]}",
            }

        return None

    # ── Status ────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_running": self.is_running,
            "interval_seconds": self.interval_seconds,
            "history": self.history[-20:],
            "last_cycle": self.history[-1] if self.history else None,
        }

    def _append(self, record: Dict[str, Any]) -> None:
        self.history.append(record)
        if len(self.history) > 50:
            self.history.pop(0)
