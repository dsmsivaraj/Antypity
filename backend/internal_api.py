from __future__ import annotations

from typing import Any, Optional

import httpx
from fastapi import FastAPI


class InternalPlatformAPI:
    def __init__(self, internal_token: str) -> None:
        self._app: Optional[FastAPI] = None
        self._internal_token = internal_token

    def bind_app(self, app: FastAPI) -> None:
        self._app = app

    async def list_models(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/internal/models")
        return payload["models"]

    async def score_agent(self, agent_name: str, task: str, context: dict[str, Any]) -> int:
        payload = await self._request(
            "POST",
            f"/internal/agents/{agent_name}/score",
            json={"task": task, "context": context},
        )
        return int(payload["score"])

    async def execute_agent(
        self,
        agent_name: str,
        task: str,
        context: dict[str, Any],
        model_profile: Optional[str],
    ) -> dict[str, Any]:
        return await self._request(
            "POST",
            f"/internal/agents/{agent_name}/execute",
            json={
                "task": task,
                "context": context,
                "model_profile": model_profile,
            },
        )

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if self._app is None:
            raise RuntimeError("Internal API is not bound to an application.")
        transport = httpx.ASGITransport(app=self._app)
        async with httpx.AsyncClient(transport=transport, base_url="http://internal") as client:
            response = await client.request(
                method,
                path,
                json=json,
                headers={"X-Internal-Token": self._internal_token},
            )
            response.raise_for_status()
            return response.json()
