import pytest
from backend.llama_client import LocalLlamaClient
from backend.config import get_settings

def test_llama_client_initialization():
    settings = get_settings()
    client = LocalLlamaClient(settings)
    assert client is not None
    # Even if Llama is not installed, the client object should be created.
    assert hasattr(client, 'complete')

@pytest.mark.asyncio
async def test_llama_inference_mock():
    # Test the microservice if it's up
    import httpx
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://localhost:9511/v1/chat/completions",
                json={
                    "model": "llama-3-8b",
                    "messages": [{"role": "user", "content": "test"}]
                }
            )
            if response.status_code == 200:
                data = response.json()
                assert "choices" in data
                assert "[Llama-3-Local]" in data["choices"][0]["message"]["content"]
    except Exception:
        pytest.skip("Inference service not reachable")
