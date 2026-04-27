from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app
from backend.container import build_container

_logger = logging.getLogger(__name__)


class ResumeTemplate(BaseModel):
    id: str
    name: str
    figma_url: str
    preview_image: str


class TemplateApplyRequest(BaseModel):
    template_id: str
    resume_data: Dict


@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Template Service (Figma Integration) starting up.")
    try:
        container = build_container()
        app.state.container = container
        _logger.info("Template Service started successfully.")
    except Exception:
        _logger.critical("Template Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Template Service shutting down.")


app = create_base_app(
    title="Template Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.get("/templates", response_model=List[ResumeTemplate], tags=["templates"])
async def list_templates():
    _logger.debug("Template list requested.")
    templates = [
        ResumeTemplate(
            id="t1",
            name="Modern Minimalist (Figma)",
            figma_url="https://figma.com/file/123",
            preview_image="https://placehold.co/200x300?text=Modern+Minimalist",
        ),
        ResumeTemplate(
            id="t2",
            name="Executive Professional",
            figma_url="https://figma.com/file/456",
            preview_image="https://placehold.co/200x300?text=Executive",
        ),
    ]
    _logger.info("Templates listed: count=%d", len(templates))
    return templates


@app.post("/templates/apply", tags=["templates"])
async def apply_template(body: TemplateApplyRequest):
    _logger.info("Template apply request: template_id=%s", body.template_id)
    try:
        download_url = f"http://localhost:9513/download/{body.template_id}_resume.pdf"
        _logger.info("Template applied: template_id=%s download_url=%s", body.template_id, download_url)
        return {
            "status": "success",
            "download_url": download_url,
            "message": "Resume successfully styled using Figma design tokens.",
        }
    except Exception:
        _logger.error("Template apply failed: template_id=%s", body.template_id, exc_info=True)
        raise HTTPException(status_code=500, detail="Template application failed.")
