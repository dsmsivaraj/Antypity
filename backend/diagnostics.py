"""DiagnosticsService — orchestrates the 4 diagnostic agents and persists results."""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


class DiagnosticsService:
    def __init__(self, health_agent, test_agent, code_agent, reporter_agent, db_client) -> None:
        self._health = health_agent
        self._test = test_agent
        self._code = code_agent
        self._reporter = reporter_agent
        self._db = db_client

    async def run_full_diagnostics(self) -> Dict[str, Any]:
        _logger.info("Starting full platform diagnostics.")
        created_at = datetime.now(timezone.utc)
        run_id = str(uuid.uuid4())

        # Health and code analysis are fast — run synchronously on the event loop thread.
        health_result = self._health.execute("run health check")
        code_result = self._code.execute("analyze code")

        # Test runner spawns a subprocess — offload to a thread to avoid blocking.
        test_context = {"skip_subprocess": True} if os.environ.get("PYTEST_CURRENT_TEST") else None
        test_result = await asyncio.to_thread(self._test.execute, "run test suite", test_context)

        all_issues: List[Dict] = (
            health_result.metadata.get("issues", [])
            + test_result.metadata.get("issues", [])
            + code_result.metadata.get("issues", [])
        )

        health_dict = health_result.metadata.get("health", {})
        tests_dict = test_result.metadata.get("tests", {})

        reporter_result = self._reporter.execute(
            "generate report",
            context={"health": health_dict, "tests": tests_dict, "issues": all_issues},
        )

        status = reporter_result.metadata.get("status", "unknown")
        summary = reporter_result.output
        completed_at = datetime.now(timezone.utc)

        record: Dict[str, Any] = {
            "id": run_id,
            "status": status,
            "health": health_dict,
            "tests": tests_dict,
            "issues": all_issues,
            "summary": summary,
            "created_at": created_at.isoformat(),
            "completed_at": completed_at.isoformat(),
        }

        if self._db and getattr(self._db, "is_configured", False):
            try:
                self._db.save_diagnostic_run(record)
            except Exception as exc:
                _logger.warning("Could not persist diagnostic run: %s", exc)

        _logger.info("Diagnostics complete: status=%s issues=%d", status, len(all_issues))
        return record

    def get_reports(self, limit: int = 10) -> List[Dict[str, Any]]:
        if not self._db or not getattr(self._db, "is_configured", False):
            return []
        try:
            return self._db.list_diagnostic_runs(limit=limit)
        except Exception as exc:
            _logger.warning("Could not list diagnostic runs: %s", exc)
            return []

    def get_latest_report(self) -> Optional[Dict[str, Any]]:
        reports = self.get_reports(limit=1)
        return reports[0] if reports else None
