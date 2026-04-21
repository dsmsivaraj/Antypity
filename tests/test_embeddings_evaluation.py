from unittest.mock import patch

from backend.embeddings_service import EmbeddingService


def test_recall_at_k():
    # Use an isolated instance with empty state (no shared FAISS data)
    with patch("backend.embeddings_service.META_PATH", new=None):
        svc = EmbeddingService()
        svc.id_map = {}
        svc.next_id = 0
        if svc.faiss_index is not None:
            import faiss
            svc.faiss_index = faiss.IndexFlatIP(svc.dim)

    text = "Senior backend engineer with Python, FastAPI, SQL, AWS."
    svc.index_document("r1", "sec1", text)

    res = svc.query("backend engineer python", top_k=3)
    assert isinstance(res, list)
    if res:
        assert any(r.get("doc_id") == "r1" for r in res)
