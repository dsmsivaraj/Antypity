from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from shared.service_utils.api_client import InternalAPIClient
from shared.service_utils.base_service import _require_internal, create_base_app
from .controller import SelfHealingController
from backend.container import build_container

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Self-Healing Orchestrator starting up.")
    try:
        container = build_container()
        app.state.container = container

        diag_url = os.environ.get("DIAGNOSTICS_SERVICE_URL", "http://localhost:9501")
        repair_url = os.environ.get("REPAIR_SERVICE_URL", "http://localhost:9502")
        token = container.settings.internal_api_token

        _logger.info(
            "Orchestrator: diag_url=%s repair_url=%s", diag_url, repair_url
        )

        diag_client = InternalAPIClient(diag_url, token)
        repair_client = InternalAPIClient(repair_url, token)
        controller = SelfHealingController(diag_client, repair_client)
        app.state.controller = controller

        await controller.start()
        _logger.info("Orchestrator self-healing loop started.")
    except Exception:
        _logger.critical("Orchestrator Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Orchestrator Service shutting down — stopping self-healing loop.")
    try:
        await controller.stop()
        _logger.info("Self-healing loop stopped cleanly.")
    except Exception:
        _logger.error("Error stopping self-healing loop.", exc_info=True)


app = create_base_app(
    title="Self-Healing Orchestrator",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.get("/self-healing/status", tags=["self-healing"])
async def get_status(request: Request):
    _logger.debug("Self-healing status requested.")
    controller: SelfHealingController = request.app.state.controller
    return controller.get_status()


@app.post("/self-healing/trigger", dependencies=[Depends(_require_internal)], tags=["self-healing"])
async def trigger_cycle(request: Request):
    _logger.info("Self-healing cycle manually triggered.")
    controller: SelfHealingController = request.app.state.controller
    try:
        result = await controller.run_cycle()
        _logger.info("Self-healing cycle complete.")
        return result
    except Exception:
        _logger.error("Self-healing cycle failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Self-healing cycle failed.")
