from fastapi.testclient import TestClient
import os
import time

import backend.vector_service as vs


def test_vector_index_query():
    client = TestClient(vs.app)
    headers = {}
    api_key = os.getenv("VECTOR_API_KEY", "devkey")
    if api_key:
        headers["X-API-Key"] = api_key

    # Index a document
    r = client.post("/index", json={"doc_id": "test-doc-1", "section_id": "s1", "text": "Senior backend engineer with Python and FastAPI."}, headers=headers)
    assert r.status_code == 200

    # Query for the document
    q = client.post("/query", json={"text": "backend Python FastAPI", "top_k": 3}, headers=headers)
    assert q.status_code == 200
    data = q.json()
    assert "results" in data
    assert len(data["results"]) >= 1
    assert any(r.get("doc_id") == "test-doc-1" for r in data["results"])

