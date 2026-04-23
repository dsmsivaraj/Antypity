"""Hybrid retrieval: BM25 sparse + dense vector search fused via Reciprocal Rank Fusion."""
from __future__ import annotations

import logging
import re
import threading
from typing import Dict, List, Optional

from .embeddings_service import get_embedding_service

_logger = logging.getLogger(__name__)

# Optional BM25
try:
    from rank_bm25 import BM25Okapi
    _HAS_BM25 = True
except ImportError:
    _HAS_BM25 = False
    _logger.warning("rank_bm25 not installed — BM25 sparse search disabled")


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _rrf_score(rank: int, k: int = 60) -> float:
    return 1.0 / (k + rank + 1)


class BM25Index:
    """Thread-safe BM25 index built lazily over the current embedding store."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._index = None
        self._docs: List[Dict] = []

    def build(self, docs: List[Dict]) -> None:
        if not _HAS_BM25 or not docs:
            return
        corpus = [_tokenize(d.get("text", "")) for d in docs]
        with self._lock:
            self._docs = docs
            self._index = BM25Okapi(corpus)

    def search(self, query: str, top_k: int = 20) -> List[Dict]:
        if not _HAS_BM25:
            return []
        with self._lock:
            if self._index is None or not self._docs:
                return []
            tokens = _tokenize(query)
            scores = self._index.get_scores(tokens)
            ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
            results = []
            for rank, (idx, score) in enumerate(ranked[:top_k]):
                doc = dict(self._docs[idx])
                doc["bm25_score"] = float(score)
                doc["bm25_rank"] = rank
                results.append(doc)
            return results

    @property
    def ready(self) -> bool:
        with self._lock:
            return self._index is not None


# Module-level BM25 index
_bm25_index = BM25Index()
_bm25_built = False
_bm25_lock = threading.Lock()


def _ensure_bm25(svc, top_k_pool: int = 200) -> None:
    global _bm25_built
    with _bm25_lock:
        if _bm25_built:
            return
        try:
            # Pull a broad set from the dense index to seed BM25
            raw = svc.query("", top_k=top_k_pool) if hasattr(svc, "query") else []
            if raw:
                _bm25_index.build(raw)
                _bm25_built = True
                _logger.info("BM25 index built with %d documents", len(raw))
        except Exception as exc:
            _logger.warning("BM25 index build failed: %s", exc)


def get_context_blocks(query: str, top_k: int = 5) -> List[Dict]:
    """Hybrid retrieval: BM25 + dense vector, fused with RRF."""
    svc = get_embedding_service()

    # Dense retrieval
    dense_k = min(top_k * 4, 40)
    try:
        dense_results = svc.query(query, top_k=dense_k)
    except Exception as exc:
        _logger.warning("Dense retrieval failed: %s", exc)
        dense_results = []

    # BM25 sparse retrieval
    _ensure_bm25(svc, top_k_pool=max(dense_k * 5, 200))
    sparse_results = _bm25_index.search(query, top_k=dense_k) if _bm25_index.ready else []

    if not dense_results and not sparse_results:
        return []

    if not sparse_results:
        # Fall back to dense-only
        return [
            {
                "doc_id": r.get("doc_id"),
                "section_id": r.get("section_id"),
                "text": r.get("text"),
                "score": r.get("score", 0.0),
                "retrieval": "dense",
            }
            for r in dense_results[:top_k]
        ]

    # RRF fusion
    scores: Dict[str, float] = {}
    meta: Dict[str, Dict] = {}

    for rank, r in enumerate(dense_results):
        key = r.get("section_id") or r.get("doc_id") or str(rank)
        scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
        meta[key] = r

    for rank, r in enumerate(sparse_results):
        key = r.get("section_id") or r.get("doc_id") or str(rank)
        scores[key] = scores.get(key, 0.0) + _rrf_score(rank)
        if key not in meta:
            meta[key] = r

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    out = []
    for key, rrf in ranked:
        doc = meta[key]
        out.append({
            "doc_id": doc.get("doc_id"),
            "section_id": doc.get("section_id"),
            "text": doc.get("text"),
            "score": round(rrf, 4),
            "retrieval": "hybrid",
        })
    return out


def invalidate_bm25() -> None:
    """Force BM25 index rebuild on next query (call after ingesting new docs)."""
    global _bm25_built
    with _bm25_lock:
        _bm25_built = False
