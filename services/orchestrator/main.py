from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request

from shared.service_utils.api_client import InternalAPIClient
from shared.service_utils.base_service import _require_internal, create_base_app
from .controller import SelfHealingController
from backend.container import build_container

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # For settings/env access
    container = build_container()
    app.state.container = container
    
    # Configure clients for peers
    # In a real environment, these come from service discovery or fixed env vars.
    diag_url = os.environ.get("DIAGNOSTICS_SERVICE_URL", "http://localhost:9501")
    repair_url = os.environ.get("REPAIR_SERVICE_URL", "http://localhost:9502")
    token = container.settings.internal_api_token
    
    diag_client = InternalAPIClient(diag_url, token)
    repair_client = InternalAPIClient(repair_url, token)
    
    controller = SelfHealingController(diag_client, repair_client)
    app.state.controller = controller
    
    # Auto-start the loop on boot
    await controller.start()
    
    _logger.info("Orchestrator service started.")
    yield
    await controller.stop()
    _logger.info("Orchestrator service shutting down.")


app = create_base_app(
    title="Self-Healing Orchestrator",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.get("/self-healing/status", tags=["self-healing"])
async def get_status(request: Request):
    controller: SelfHealingController = request.app.state.controller
    return controller.get_status()


@app.post("/self-healing/trigger", dependencies=[Depends(_require_internal)], tags=["self-healing"])
async def trigger_cycle(request: Request):
    controller: SelfHealingController = request.app.state.controller
    result = await controller.run_cycle()
    return result
