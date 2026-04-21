from backend.retrieval import get_context_blocks


def test_get_context_blocks_basic():
    # Should not raise
    blocks = get_context_blocks('test query does not match any docs', top_k=3)
    assert isinstance(blocks, list)

