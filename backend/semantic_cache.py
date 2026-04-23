"""Semantic cache for LLM responses using cosine similarity.

Caches (query, response) pairs. On a cache hit (similarity >= threshold),
returns the stored response without calling the LLM.
"""
from __future__ import annotations

import math
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import List, Optional

_logger = logging.getLogger(__name__)


def _cosine(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


@dataclass
class _CacheEntry:
    query_embedding: List[float]
    response: str
    created_at: float = field(default_factory=time.monotonic)
    hits: int = 0


class SemanticCache:
    """In-memory semantic cache with TTL and max-size eviction."""

    def __init__(
        self,
        similarity_threshold: float = 0.92,
        ttl_seconds: float = 3600.0,
        max_entries: int = 500,
    ) -> None:
        self.similarity_threshold = similarity_threshold
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._entries: List[_CacheEntry] = []
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, query_embedding: List[float]) -> Optional[str]:
        now = time.monotonic()
        with self._lock:
            self._evict_expired(now)
            best_score = 0.0
            best_entry: Optional[_CacheEntry] = None
            for entry in self._entries:
                score = _cosine(query_embedding, entry.query_embedding)
                if score > best_score:
                    best_score = score
                    best_entry = entry
            if best_entry is not None and best_score >= self.similarity_threshold:
                best_entry.hits += 1
                self._hits += 1
                _logger.debug("SemanticCache HIT (similarity=%.3f)", best_score)
                return best_entry.response
            self._misses += 1
            return None

    def put(self, query_embedding: List[float], response: str) -> None:
        with self._lock:
            if len(self._entries) >= self.max_entries:
                # evict LRU (lowest hit count, oldest)
                self._entries.sort(key=lambda e: (e.hits, e.created_at))
                self._entries.pop(0)
            self._entries.append(_CacheEntry(query_embedding=query_embedding, response=response))

    def _evict_expired(self, now: float) -> None:
        cutoff = now - self.ttl_seconds
        self._entries = [e for e in self._entries if e.created_at >= cutoff]

    def get_stats(self) -> dict:
        with self._lock:
            total = self._hits + self._misses
            return {
                "entries": len(self._entries),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": round(self._hits / total, 3) if total else 0.0,
                "threshold": self.similarity_threshold,
                "ttl_seconds": self.ttl_seconds,
            }

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0


# Module-level singleton
_cache: Optional[SemanticCache] = None
_cache_lock = threading.Lock()


def get_semantic_cache(
    similarity_threshold: float = 0.92,
    ttl_seconds: float = 3600.0,
    max_entries: int = 500,
) -> SemanticCache:
    global _cache
    with _cache_lock:
        if _cache is None:
            _cache = SemanticCache(
                similarity_threshold=similarity_threshold,
                ttl_seconds=ttl_seconds,
                max_entries=max_entries,
            )
        return _cache
