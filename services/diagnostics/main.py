from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Request

from shared.service_utils.base_service import _require_internal, create_base_app
from .agents.diagnostics_agent import (
    CodeAnalyzerAgent,
    DiagnosticsReporterAgent,
    HealthCheckAgent,
    TestRunnerAgent,
)
from backend.container import build_container

_logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # For now, reuse the backend container to get DB/LLM clients.
    # In a full microservice split, these would be separate or proxied.
    container = build_container()
    app.state.container = container
    
    # Initialize diagnostic agents
    app.state.health_agent = HealthCheckAgent(
        db_client=container.database_client,
        llm_client=container.llm_client,
        registry=container.registry,
        store=container.store,
    )
    app.state.test_agent = TestRunnerAgent()
    app.state.code_agent = CodeAnalyzerAgent()
    app.state.reporter_agent = DiagnosticsReporterAgent()
    
    _logger.info("Diagnostics service started.")
    yield
    _logger.info("Diagnostics service shutting down.")


app = create_base_app(
    title="Diagnostics Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/diagnostics/health", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def run_health_check(request: Request):
    agent: HealthCheckAgent = request.app.state.health_agent
    result = agent.execute("run health check")
    return result


@app.post("/diagnostics/test", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def run_test_suite(request: Request):
    agent: TestRunnerAgent = request.app.state.test_agent
    result = agent.execute("run tests")
    return result


@app.post("/diagnostics/code", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def run_code_analysis(request: Request):
    agent: CodeAnalyzerAgent = request.app.state.code_agent
    result = agent.execute("scan code")
    return result


@app.get("/diagnostics/report", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def get_diagnostic_report(request: Request):
    health_agent: HealthCheckAgent = request.app.state.health_agent
    test_agent: TestRunnerAgent = request.app.state.test_agent
    code_agent: CodeAnalyzerAgent = request.app.state.code_agent
    reporter_agent: DiagnosticsReporterAgent = request.app.state.reporter_agent
    
    health_res = health_agent.execute("run health check")
    test_res = test_agent.execute("run tests")
    code_res = code_agent.execute("scan code")
    
    # Aggregate context for reporter
    context = {
        "health": health_res.metadata.get("health", {}),
        "tests": test_res.metadata.get("tests", {}),
        "issues": (
            health_res.metadata.get("issues", []) +
            test_res.metadata.get("issues", []) +
            code_res.metadata.get("issues", [])
        )
    }
    
    report = reporter_agent.execute("generate report", context=context)
    return report
