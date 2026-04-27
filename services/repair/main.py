from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import Depends, FastAPI, HTTPException, Request

from shared.service_utils.base_service import _require_internal, create_base_app
from .agents.repair_agents import BugFixAgent, SelfHealingAgent
from backend.container import build_container

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Repair Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        app.state.healing_agent = SelfHealingAgent()
        app.state.bug_fix_agent = BugFixAgent(llm_client=container.llm_client)
        _logger.info("Repair Service started successfully.")
    except Exception:
        _logger.critical("Repair Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Repair Service shutting down.")


app = create_base_app(
    title="Repair Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/repair/service", dependencies=[Depends(_require_internal)], tags=["repair"])
async def run_service_repair(request: Request, body: Dict):
    service_name = body.get("service_name")
    if not service_name:
        _logger.warning("Service repair request missing service_name.")
        raise HTTPException(status_code=400, detail="service_name is required.")

    _logger.info("Service repair triggered: service=%s", service_name)
    agent: SelfHealingAgent = request.app.state.healing_agent

    try:
        result = agent.execute(f"restart {service_name}")
        _logger.info("Service repair complete: service=%s", service_name)
        return result
    except Exception:
        _logger.error("Service repair failed: service=%s", service_name, exc_info=True)
        raise HTTPException(status_code=500, detail="Service repair failed.")


@app.post("/repair/code", dependencies=[Depends(_require_internal)], tags=["repair"])
async def run_code_repair(request: Request, body: Dict):
    issue = body.get("issue")
    if not issue:
        _logger.warning("Code repair request missing issue field.")
        raise HTTPException(status_code=400, detail="issue is required.")

    _logger.info("Code repair triggered: issue=%s", str(issue)[:200])
    agent: BugFixAgent = request.app.state.bug_fix_agent

    try:
        result = agent.execute("fix code bug", context={"issue": issue})
        _logger.info("Code repair complete.")
        return result
    except Exception:
        _logger.error("Code repair failed: issue=%s", str(issue)[:200], exc_info=True)
        raise HTTPException(status_code=500, detail="Code repair failed.")
