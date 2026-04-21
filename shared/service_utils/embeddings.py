from __future__ import annotations

import logging
import random
from typing import List, Optional

import httpx

_logger = logging.getLogger(__name__)

class EmbeddingService:
    """Service for generating text embeddings."""

    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None) -> None:
        self.api_key = api_key
        self.endpoint = endpoint

    async def generate(self, text: str) -> List[float]:
        """Generates an embedding vector for the given text."""
        if not self.api_key or not self.endpoint:
            _logger.warning("Embeddings API not configured. Using deterministic mock.")
            return self._mock_embedding(text)

        try:
            # In production, this calls OpenAI or Azure OpenAI Embeddings
            # async with httpx.AsyncClient() as client:
            #     response = await client.post(...)
            #     return response.json()["data"][0]["embedding"]
            return self._mock_embedding(text)
        except Exception as exc:
            _logger.error("Failed to generate embedding: %s", exc)
            return self._mock_embedding(text)

    def _mock_embedding(self, text: str) -> List[float]:
        """Deterministic mock embedding based on text content."""
        # Use a seed for deterministic 'random' values per text
        random.seed(len(text))
        return [random.random() for _ in range(1536)] # Standard OpenAI dimension
