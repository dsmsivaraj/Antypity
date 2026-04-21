from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
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
    container = build_container()
    app.state.container = container
    _logger.info("Template Service (Figma Integration) started.")
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
    return [
        ResumeTemplate(
            id="t1", 
            name="Modern Minimalist (Figma)", 
            figma_url="https://figma.com/file/123", 
            preview_image="https://placehold.co/200x300?text=Modern+Minimalist"
        ),
        ResumeTemplate(
            id="t2", 
            name="Executive Professional", 
            figma_url="https://figma.com/file/456", 
            preview_image="https://placehold.co/200x300?text=Executive"
        ),
    ]

@app.post("/templates/apply", tags=["templates"])
async def apply_template(body: TemplateApplyRequest):
    _logger.info("Applying template %s to resume data.", body.template_id)
    # Simulate fetching Figma design tokens and rendering a document.
    return {
        "status": "success",
        "download_url": f"http://localhost:9513/download/{body.template_id}_resume.pdf",
        "message": "Resume successfully styled using Figma design tokens."
    }
