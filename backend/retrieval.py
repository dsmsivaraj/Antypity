from __future__ import annotations

from typing import List, Dict
from .embeddings_service import get_embedding_service


def get_context_blocks(query: str, top_k: int = 5) -> List[Dict[str, object]]:
    svc = get_embedding_service()
    results = svc.query(query, top_k=top_k)
    # Ensure fields
    out = []
    for r in results:
        out.append({
            "doc_id": r.get("doc_id"),
            "section_id": r.get("section_id"),
            "text": r.get("text"),
            "score": r.get("score", 0.0),
        })
    return out
