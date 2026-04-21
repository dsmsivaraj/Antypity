from __future__ import annotations

import os
import logging
from typing import List, Optional

import requests

_logger = logging.getLogger(__name__)


class RemoteEmbeddingService:
    def __init__(self, base_url: Optional[str] = None, api_key: Optional[str] = None) -> None:
        self.base_url = base_url or os.getenv("VECTOR_SERVICE_URL")
        if not self.base_url:
            raise ValueError("VECTOR_SERVICE_URL not set for RemoteEmbeddingService")
        self.api_key = api_key or os.getenv("VECTOR_API_KEY")
        self.session = requests.Session()
        if self.api_key:
            self.session.headers.update({"X-API-Key": self.api_key})

    def _url(self, path: str) -> str:
        return f"{self.base_url.rstrip('/')}{path}"

    def encode(self, texts: List[str]) -> List[List[float]]:
        try:
            resp = self.session.post(self._url("/encode"), json={"texts": texts}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("embeddings", [])
        except Exception as exc:
            _logger.warning("Remote encode failed: %s", exc)
            return [[0.0] for _ in texts]

    def index_document(self, doc_id: str, section_id: str, text: str) -> None:
        try:
            resp = self.session.post(self._url("/index"), json={"doc_id": doc_id, "section_id": section_id, "text": text}, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            _logger.warning("Remote index failed: %s", exc)

    def query(self, text: str, top_k: int = 5):
        try:
            resp = self.session.post(self._url("/query"), json={"text": text, "top_k": top_k}, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data.get("results", [])
        except Exception as exc:
            _logger.warning("Remote query failed: %s", exc)
            return []
