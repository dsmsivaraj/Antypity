from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from .database import PostgreSQLDatabaseClient

_logger = logging.getLogger(__name__)


class MetricsService:
    """Records per-agent execution metrics to PostgreSQL when available."""

    def __init__(self, db: Optional[PostgreSQLDatabaseClient] = None) -> None:
        self._db = db
        self._enabled = db is not None and db.is_configured

    @property
    def enabled(self) -> bool:
        return self._enabled

    def record(self, agent_name: str, used_llm: bool, failed: bool = False) -> None:
        if not self._enabled:
            return
        try:
            self._db.record_metric(  # type: ignore[union-attr]
                agent_name=agent_name, used_llm=used_llm, failed=failed
            )
        except Exception as exc:
            _logger.warning("Failed to record metric for agent '%s': %s", agent_name, exc)

    def list_all(self) -> List[Dict[str, Any]]:
        if not self._enabled or self._db is None:
            return []
        try:
            return self._db.list_metrics()
        except Exception as exc:
            _logger.warning("Failed to list metrics: %s", exc)
            return []
