from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, Optional

from fastapi import Depends, FastAPI, Request

from shared.service_utils.base_service import _require_internal, create_base_app
from .agents.repair_agents import BugFixAgent, SelfHealingAgent
from backend.container import build_container

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    
    app.state.healing_agent = SelfHealingAgent()
    app.state.bug_fix_agent = BugFixAgent(llm_client=container.llm_client)
    
    _logger.info("Repair service started.")
    yield
    _logger.info("Repair service shutting down.")


app = create_base_app(
    title="Repair Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/repair/service", dependencies=[Depends(_require_internal)], tags=["repair"])
async def run_service_repair(request: Request, body: Dict):
    agent: SelfHealingAgent = request.app.state.healing_agent
    service_name = body.get("service_name")
    result = agent.execute(f"restart {service_name}")
    return result


@app.post("/repair/code", dependencies=[Depends(_require_internal)], tags=["repair"])
async def run_code_repair(request: Request, body: Dict):
    agent: BugFixAgent = request.app.state.bug_fix_agent
    issue = body.get("issue")
    result = agent.execute("fix code bug", context={"issue": issue})
    return result
