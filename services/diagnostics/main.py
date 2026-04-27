from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request

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
    _logger.info("Diagnostics Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        app.state.health_agent = HealthCheckAgent(
            db_client=container.database_client,
            llm_client=container.llm_client,
            registry=container.registry,
            store=container.store,
        )
        app.state.test_agent = TestRunnerAgent()
        app.state.code_agent = CodeAnalyzerAgent()
        app.state.reporter_agent = DiagnosticsReporterAgent()
        _logger.info("Diagnostics Service started successfully.")
    except Exception:
        _logger.critical("Diagnostics Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Diagnostics Service shutting down.")


app = create_base_app(
    title="Diagnostics Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/diagnostics/health", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def run_health_check(request: Request):
    _logger.info("Health check triggered.")
    agent: HealthCheckAgent = request.app.state.health_agent
    try:
        result = agent.execute("run health check")
        _logger.info("Health check complete: used_llm=%s", result.used_llm)
        return result
    except Exception:
        _logger.error("Health check failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Health check failed.")


@app.post("/diagnostics/test", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def run_test_suite(request: Request):
    _logger.info("Test suite triggered.")
    agent: TestRunnerAgent = request.app.state.test_agent
    try:
        result = agent.execute("run tests")
        _logger.info("Test suite complete.")
        return result
    except Exception:
        _logger.error("Test suite failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Test suite failed.")


@app.post("/diagnostics/code", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def run_code_analysis(request: Request):
    _logger.info("Code analysis triggered.")
    agent: CodeAnalyzerAgent = request.app.state.code_agent
    try:
        result = agent.execute("scan code")
        _logger.info("Code analysis complete.")
        return result
    except Exception:
        _logger.error("Code analysis failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Code analysis failed.")


@app.get("/diagnostics/report", dependencies=[Depends(_require_internal)], tags=["diagnostics"])
async def get_diagnostic_report(request: Request):
    _logger.info("Diagnostic report requested.")
    health_agent: HealthCheckAgent = request.app.state.health_agent
    test_agent: TestRunnerAgent = request.app.state.test_agent
    code_agent: CodeAnalyzerAgent = request.app.state.code_agent
    reporter_agent: DiagnosticsReporterAgent = request.app.state.reporter_agent

    try:
        health_res = health_agent.execute("run health check")
        test_res = test_agent.execute("run tests")
        code_res = code_agent.execute("scan code")

        context = {
            "health": health_res.metadata.get("health", {}),
            "tests": test_res.metadata.get("tests", {}),
            "issues": (
                health_res.metadata.get("issues", [])
                + test_res.metadata.get("issues", [])
                + code_res.metadata.get("issues", [])
            ),
        }
        total_issues = len(context["issues"])
        _logger.info("Diagnostic report compiled: total_issues=%d", total_issues)

        report = reporter_agent.execute("generate report", context=context)
        _logger.info("Diagnostic report generated.")
        return report
    except Exception:
        _logger.error("Diagnostic report generation failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Diagnostic report failed.")
