from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx

_logger = logging.getLogger(__name__)


class InternalAPIClient:
    """Shared HTTP client for inter-service communication."""

    def __init__(self, base_url: str, internal_token: str, timeout: int = 60) -> None:
        self.base_url = base_url.rstrip("/")
        self.internal_token = internal_token
        self.timeout = timeout

    async def request(
        self,
        method: str,
        path: str,
        json: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> Any:
        url = f"{self.base_url}/{path.lstrip('/')}"
        headers = {"X-Internal-Token": self.internal_token}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    json=json,
                    params=params,
                    headers=headers,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                _logger.error(
                    "Inter-service request failed: %s %s -> %s %s",
                    method, url, exc.response.status_code, exc.response.text
                )
                raise
            except Exception as exc:
                _logger.error("Inter-service request error: %s %s -> %s", method, url, exc)
                raise

    async def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Any:
        return await self.request("GET", path, params=params)

    async def post(self, path: str, json: Optional[Dict[str, Any]] = None) -> Any:
        return await self.request("POST", path, json=json)
