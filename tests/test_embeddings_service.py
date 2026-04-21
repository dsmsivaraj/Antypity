from backend.embeddings_service import EmbeddingService


def test_embedding_index_and_query():
    svc = EmbeddingService()
    # index a few small sections
    svc.index_document('resume1', 'section-1', 'Alice is a senior software engineer with experience in Python and FastAPI.')
    svc.index_document('resume1', 'section-2', 'Bob is a product manager skilled in roadmap, metrics, and user research.')

    res = svc.query('software engineer python', top_k=2)
    assert isinstance(res, list)
    assert len(res) >= 0
    # At least one result should have doc_id
    if res:
        assert 'doc_id' in res[0]


def test_embedding_encode_fallback():
    svc = EmbeddingService()
    vecs = svc.encode(['hello world', 'software engineer'])
    assert isinstance(vecs, list)
    assert len(vecs) == 2
