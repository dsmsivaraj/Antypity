from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

_logger = logging.getLogger(__name__)

# Optional heavy deps
try:
    from sentence_transformers import SentenceTransformer
except Exception:
    SentenceTransformer = None

try:
    import faiss
except Exception:
    faiss = None

# Fallback simple index
from .config import get_settings
from .embeddings import VectorIndex, add_resume_section_embeddings, query_resume_sections, text_to_vector
import os
from .remote_vector_client import RemoteEmbeddingService
from .metrics import DBMetricsMixin, count_encode, count_query, record_retrieval_hit, timeit

DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
META_PATH = DATA_DIR / "embeddings_meta.json"


class EmbeddingService(DBMetricsMixin):
    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        database_client=None,
    ) -> None:
        self.settings = get_settings()
        self.model_name = model_name
        self._db = database_client if getattr(database_client, "is_configured", False) else None
        self.model = None
        self.faiss_index = None
        self.id_map: Dict[int, Dict[str, str]] = {}
        self.next_id = 0
        self.dim = 384

        if SentenceTransformer is not None:
            try:
                self.model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception as exc:
                _logger.warning("Failed to load sentence-transformers model: %s", exc)
                self.model = None

        if self.model is not None and faiss is not None:
            try:
                # initialize empty index; will be rebuilt as needed
                self.dim = self.model.get_sentence_embedding_dimension()
                self.faiss_index = faiss.IndexFlatIP(self.dim)
                # mapping persists in META_PATH
                if META_PATH.exists():
                    try:
                        data = json.loads(META_PATH.read_text(encoding='utf-8'))
                        self.id_map = {int(k): v for k, v in data.get("id_map", {}).items()}
                        self.next_id = max(self.id_map.keys()) + 1 if self.id_map else 0
                        _logger.info("Loaded embeddings metadata: %d entries", len(self.id_map))
                    except Exception:
                        self.id_map = {}
                else:
                    self.id_map = {}
            except Exception as exc:
                _logger.warning("Failed to initialize FAISS index: %s", exc)
                self.faiss_index = None

        # Fallback to simple VectorIndex
        self.fallback_index = VectorIndex()

    def status(self) -> Dict[str, object]:
        backend = "token-index"
        if self._pgvector_ready:
            backend = "pgvector"
        elif self.faiss_index is not None and self.model is not None:
            backend = "faiss"
        if self._pgvector_ready and self._db is not None:
            doc_count = self._db.count_resume_embeddings()
        else:
            doc_count = len(self.id_map) if self.id_map else len(getattr(self.fallback_index, "index", {}))
        return {
            "backend": backend,
            "model_name": self.model_name,
            "model_loaded": self.model is not None,
            "pgvector_enabled": self._pgvector_ready,
            "faiss_enabled": self.faiss_index is not None,
            "fallback_enabled": self.settings.retrieval_local_fallback_enabled,
            "document_count": int(doc_count),
        }

    @property
    def _pgvector_ready(self) -> bool:
        return bool(self._db is not None and self.model is not None and self._db.has_pgvector())

    def set_database_client(self, database_client) -> None:
        self._db = database_client if getattr(database_client, "is_configured", False) else None

    def _persist_meta(self):
        try:
            META_PATH.write_text(json.dumps({"id_map": {str(k): v for k, v in self.id_map.items()}}, ensure_ascii=False))
        except Exception:
            pass

    def encode(self, texts: List[str]) -> List[List[float]]:
        count_encode()
        if self.model is not None:
            @timeit
            def _enc(t):
                return [list(map(float, v)) for v in self.model.encode(t, show_progress_bar=False)]

            return _enc(texts)
        # fallback: return empty vectors (not used by fallback index)
        return [[0.0] for _ in texts]

    def index_document(self, doc_id: str, section_id: str, text: str) -> None:
        """Index a document section. Uses pgvector first, then FAISS, then local token index."""
        if self._pgvector_ready:
            try:
                vec = self.encode([text])[0]
                if any(vec):
                    self._db.upsert_resume_embedding(  # type: ignore[union-attr]
                        doc_id=doc_id,
                        section_id=section_id,
                        excerpt=text,
                        embedding=vec,
                    )
                    return
            except Exception as exc:
                _logger.warning("pgvector upsert failed: %s", exc)
        if self.faiss_index is not None and self.model is not None:
            vec = self.model.encode([text])[0].astype('float32')
            try:
                self.faiss_index.add(vec.reshape(1, -1))
                self.id_map[self.next_id] = {"doc_id": doc_id, "section_id": section_id, "text": text[:2000]}
                self.next_id += 1
                self._persist_meta()
                return
            except Exception as exc:
                _logger.warning("FAISS add failed: %s", exc)
        # Fallback
        add_resume_section_embeddings(doc_id, section_id, text)

    def query(self, text: str, top_k: int = 5):
        """Query the index. Returns list of dicts with doc_id, section_id, text, score.
        """
        import time

        count_query()
        start = time.time()
        results: List[Dict[str, object]] = []
        used_pgvector = False
        used_faiss = False
        candidate_pool = max(top_k, self.settings.retrieval_candidate_pool_size)
        if self._pgvector_ready:
            try:
                q = self.encode([text])[0]
                if any(q):
                    vector_results = self._db.query_resume_embeddings(  # type: ignore[union-attr]
                        embedding=q,
                        top_k=candidate_pool,
                    )
                    lexical_results = self._db.lexical_search_resume_embeddings(  # type: ignore[union-attr]
                        keywords=self._keywords(text),
                        top_k=candidate_pool,
                    )
                    results = self._rerank_results(vector_results, lexical_results, top_k=top_k)
                    used_pgvector = True
            except Exception as exc:
                _logger.warning("pgvector query failed: %s", exc)
        if self.faiss_index is not None and self.model is not None and self.id_map:
            q = self.model.encode([text])[0].astype('float32')
            try:
                if not results:
                    faiss_results: List[Dict[str, object]] = []
                    D, I = self.faiss_index.search(q.reshape(1, -1), top_k)
                    for score, idx in zip(D[0], I[0]):
                        if idx < 0:
                            continue
                        meta = self.id_map.get(int(idx), {})
                        faiss_results.append({
                            "doc_id": meta.get("doc_id"),
                            "section_id": meta.get("section_id"),
                            "text": meta.get("text"),
                            "score": float(score),
                        })
                    results = self._rerank_results(faiss_results, [], top_k=top_k)
                    used_faiss = True
            except Exception as exc:
                _logger.warning("FAISS search failed: %s", exc)

        if not results:
            if self.settings.retrieval_local_fallback_enabled:
                results = query_resume_sections(text, top_k=top_k)

        latency_ms = (time.time() - start) * 1000.0
        try:
            record_retrieval_hit(bool(results))
            self.record_retrieval(
                query_text=text,
                top_k=top_k,
                results=results,
                latency_ms=latency_ms,
                used_faiss=(used_faiss or used_pgvector),
                empty_context=len(results) == 0,
            )
        except Exception:
            pass

        return results

    def _keywords(self, text: str) -> List[str]:
        ranked = sorted(text_to_vector(text).items(), key=lambda item: item[1], reverse=True)
        return [token for token, _ in ranked[:8]]

    def _rerank_results(
        self,
        vector_results: List[Dict[str, object]],
        lexical_results: List[Dict[str, object]],
        *,
        top_k: int,
    ) -> List[Dict[str, object]]:
        merged: Dict[str, Dict[str, object]] = {}
        for row in vector_results:
            key = f"{row.get('doc_id')}:{row.get('section_id')}"
            merged[key] = {
                "doc_id": row.get("doc_id"),
                "section_id": row.get("section_id"),
                "text": row.get("text"),
                "vector_score": float(row.get("score", 0.0)),
                "lexical_score": 0.0,
            }
        for row in lexical_results:
            key = f"{row.get('doc_id')}:{row.get('section_id')}"
            current = merged.setdefault(
                key,
                {
                    "doc_id": row.get("doc_id"),
                    "section_id": row.get("section_id"),
                    "text": row.get("text"),
                    "vector_score": 0.0,
                    "lexical_score": 0.0,
                },
            )
            current["lexical_score"] = float(row.get("score", 0.0))
            current["text"] = current.get("text") or row.get("text")

        reranked: List[Dict[str, object]] = []
        for item in merged.values():
            lexical = float(item.get("lexical_score", 0.0))
            vector = float(item.get("vector_score", 0.0))
            combined = (vector * 0.75) + (min(lexical, 5.0) / 5.0 * 0.25)
            reranked.append(
                {
                    "doc_id": item.get("doc_id"),
                    "section_id": item.get("section_id"),
                    "text": item.get("text"),
                    "score": combined,
                    "vector_score": vector,
                    "lexical_score": lexical,
                }
            )
        reranked.sort(key=lambda row: float(row.get("score", 0.0)), reverse=True)
        return reranked[:top_k]

    def migrate_local_embeddings(self) -> int:
        if not self._pgvector_ready:
            return 0
        source_rows: Dict[str, Dict[str, str]] = {}
        for key, value in getattr(self.fallback_index, "index", {}).items():
            source_rows[key] = {
                "doc_id": str(value.get("doc_id", "")),
                "section_id": str(value.get("section_id", "")),
                "text": str(value.get("text", "")),
            }
        for _, value in self.id_map.items():
            key = f"{value.get('doc_id')}:{value.get('section_id')}"
            source_rows.setdefault(
                key,
                {
                    "doc_id": str(value.get("doc_id", "")),
                    "section_id": str(value.get("section_id", "")),
                    "text": str(value.get("text", "")),
                },
            )

        migrated = 0
        for row in source_rows.values():
            if not row["doc_id"] or not row["section_id"] or not row["text"]:
                continue
            try:
                vec = self.encode([row["text"]])[0]
                if not any(vec):
                    continue
                ok = self._db.upsert_resume_embedding(  # type: ignore[union-attr]
                    doc_id=row["doc_id"],
                    section_id=row["section_id"],
                    excerpt=row["text"],
                    embedding=vec,
                )
                if ok:
                    migrated += 1
            except Exception as exc:
                _logger.warning(
                    "Failed migrating local embedding for %s:%s: %s",
                    row["doc_id"],
                    row["section_id"],
                    exc,
                )
        return migrated


# Singleton
_default_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    global _default_service
    if _default_service is None:
        # If VECTOR_SERVICE_URL is set, use remote client wrapper
        vector_url = os.getenv("VECTOR_SERVICE_URL")
        if vector_url:
            _default_service = RemoteEmbeddingService(vector_url)
        else:
            _default_service = EmbeddingService()
    return _default_service


def configure_embedding_service(database_client=None, model_name: str = "sentence-transformers/all-MiniLM-L6-v2") -> EmbeddingService:
    global _default_service
    vector_url = os.getenv("VECTOR_SERVICE_URL")
    if _default_service is None:
        if vector_url:
            _default_service = RemoteEmbeddingService(vector_url)
            # remote client won't use DB client locally
        else:
            _default_service = EmbeddingService(model_name=model_name, database_client=database_client)
    else:
        # if local service, set db client
        if isinstance(_default_service, EmbeddingService):
            _default_service.set_database_client(database_client)
    return _default_service
