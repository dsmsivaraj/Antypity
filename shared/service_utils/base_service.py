from __future__ import annotations

import logging
from typing import Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

_logger = logging.getLogger(__name__)


def _require_internal(
    request: Request,
    x_internal_token: Optional[str] = Header(None, alias="X-Internal-Token"),
) -> bool:
    """Authentication dependency for inter-service communication."""
    container = getattr(request.app.state, "container", None)
    if not container:
        raise HTTPException(status_code=500, detail="App container not initialized.")

    internal_token = getattr(container.settings, "internal_api_token", "default-internal-token")
    if x_internal_token != internal_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token.",
        )
    return True


def create_base_app(
    title: str,
    version: str,
    cors_origins: list[str],
    lifespan=None,
) -> FastAPI:
    """Factory to create a FastAPI app with standardized middleware and auth."""
    app = FastAPI(
        title=title,
        version=version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health", tags=["meta"])
    async def health():
        return {"status": "ok", "service": title, "version": version}

    return app
