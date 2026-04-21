from __future__ import annotations

import logging
import time
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

from .database import PostgreSQLDatabaseClient

_logger = logging.getLogger(__name__)

# Simple in-process counters for quick instrumentation in dev.
_COUNTERS: Dict[str, int] = {"encodes": 0, "queries": 0, "retrieval_hits": 0, "retrieval_calls": 0}


def count_encode() -> None:
    _COUNTERS["encodes"] += 1


def count_query() -> None:
    _COUNTERS["queries"] += 1


def record_retrieval_hit(hit: bool) -> None:
    _COUNTERS["retrieval_calls"] += 1
    if hit:
        _COUNTERS["retrieval_hits"] += 1


class Timer:
    def __init__(self, name: str = "timer"):
        self.name = name
        self._start = None

    def __enter__(self):
        self._start = time.time()
        return self

    def __exit__(self, exc_type, exc, tb):
        elapsed = time.time() - (self._start or time.time())
        _logger.debug("Timer %s elapsed: %.3fs", self.name, elapsed)


def timeit(func):
    def wrapper(*args, **kwargs):
        start = time.time()
        out = func(*args, **kwargs)
        elapsed = time.time() - start
        _logger.debug("%s took %.3fs", func.__name__, elapsed)
        return out

    return wrapper


class MetricsService:
    """Records per-agent execution metrics to PostgreSQL when available.

    Deprecated: prefer using the module-level helpers in simple dev scenarios. MetricsService
    still wraps DB-backed metric recording for production use.
    """

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


def current_counters() -> Dict[str, int]:
    return dict(_COUNTERS)


class DBMetricsMixin:
    """Optional mixin helpers to persist retrieval metrics to the configured DB."""

    def record_retrieval(self, query_text: str, top_k: int, results: list, latency_ms: float, used_faiss: bool, empty_context: bool = False) -> None:
        """Persist a retrieval_metrics row when DB is configured.

        Attempts multiple DB client interfaces for compatibility.
        """
        if not hasattr(self, '_db') or getattr(self, '_db', None) is None:
            return
        try:
            db = getattr(self, '_db')
            # Try common helper first
            if hasattr(db, 'record_retrieval_metric'):
                try:
                    db.record_retrieval_metric(
                        query_text=query_text,
                        top_k=top_k,
                        result_count=len(results),
                        avg_score=float(sum(r.get('score', 0.0) for r in results) / (len(results) or 1)),
                        latency_ms=latency_ms,
                        used_faiss=used_faiss,
                        empty_context=empty_context,
                    )
                    return
                except Exception:
                    pass
            # Fallback: raw SQL via cursor if connection available
            conn = None
            if hasattr(db, 'conn'):
                conn = getattr(db, 'conn')
            elif hasattr(db, 'engine'):
                # SQLAlchemy-style
                engine = getattr(db, 'engine')
                with engine.connect() as conn:
                    conn.execute(
                        "INSERT INTO retrieval_metrics (query_text, top_k, result_count, avg_score, latency_ms, used_faiss, empty_context) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (query_text, top_k, len(results), float(sum(r.get('score', 0.0) for r in results) / (len(results) or 1)), latency_ms, used_faiss, empty_context),
                    )
                    return
            if conn is not None:
                cur = conn.cursor()
                cur.execute(
                    "INSERT INTO retrieval_metrics (query_text, top_k, result_count, avg_score, latency_ms, used_faiss, empty_context) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (query_text, top_k, len(results), float(sum(r.get('score', 0.0) for r in results) / (len(results) or 1)), latency_ms, used_faiss, empty_context),
                )
                conn.commit()
        except Exception as exc:
            _logger.debug("Failed to persist retrieval metric: %s", exc)
