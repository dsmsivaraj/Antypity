from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
from backend.container import build_container

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class CoverLetterRequest(BaseModel):
    resume_text: str
    jd_text: str
    tone: Optional[str] = "professional"

class OutreachRequest(BaseModel):
    recipient_email: str
    subject: str
    body: str

class ContactInfo(BaseModel):
    name: str
    role: str
    email: Optional[str]


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    _logger.info("Outreach service started.")
    yield
    _logger.info("Outreach service shutting down.")


app = create_base_app(
    title="Outreach Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/outreach/cover-letter", tags=["outreach"])
async def generate_cover_letter(request: Request, body: CoverLetterRequest):
    container = request.app.state.container
    
    prompt = f"Write a {body.tone} cover letter based on:\nResume: {body.resume_text[:1000]}\nJD: {body.jd_text[:1000]}"
    
    profile, llm_result = container.model_router.complete(
        model_profile="reviewer",
        prompt=prompt,
        system_prompt="You are a persuasive career coach."
    )
    
    return {"cover_letter": llm_result.content}


@app.post("/outreach/find-contact", response_model=List[ContactInfo], tags=["outreach"])
async def find_contact(request: Request, company: str):
    # Simulated contact finding
    return [
        ContactInfo(name="Jane Doe", role="Senior Recruiter", email="jane.doe@company.com"),
        ContactInfo(name="John Smith", role="Engineering Manager", email=None)
    ]


@app.post("/outreach/send-email", tags=["outreach"])
async def send_email(request: Request, body: OutreachRequest):
    # In production, this would use google-api-python-client with OAuth token
    _logger.info("Sending email to %s", body.recipient_email)
    return {"status": "sent", "recipient": body.recipient_email}
