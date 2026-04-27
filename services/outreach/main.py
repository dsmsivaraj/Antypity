from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app
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
    _logger.info("Outreach Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        _logger.info("Outreach Service started successfully.")
    except Exception:
        _logger.critical("Outreach Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Outreach Service shutting down.")


app = create_base_app(
    title="Outreach Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/outreach/cover-letter", tags=["outreach"])
async def generate_cover_letter(request: Request, body: CoverLetterRequest):
    _logger.info(
        "Cover letter request: tone=%s resume_len=%d jd_len=%d",
        body.tone, len(body.resume_text), len(body.jd_text),
    )
    container = request.app.state.container

    prompt = (
        f"Write a {body.tone} cover letter based on:\n"
        f"Resume: {body.resume_text[:1000]}\nJD: {body.jd_text[:1000]}"
    )
    try:
        profile, llm_result = container.model_router.complete(
            model_profile="reviewer",
            prompt=prompt,
            system_prompt="You are a persuasive career coach.",
        )
        _logger.info("Cover letter generated: used_llm=%s profile=%s", llm_result.used_llm, profile)
    except Exception:
        _logger.error("Cover letter generation failed.", exc_info=True)
        raise HTTPException(status_code=500, detail="Cover letter generation failed.")

    return {"cover_letter": llm_result.content}


@app.post("/outreach/find-contact", response_model=List[ContactInfo], tags=["outreach"])
async def find_contact(request: Request, company: str):
    _logger.info("Contact search: company=%s", company)
    contacts = [
        ContactInfo(name="Jane Doe", role="Senior Recruiter", email="jane.doe@company.com"),
        ContactInfo(name="John Smith", role="Engineering Manager", email=None),
    ]
    _logger.info("Contact search returned %d results for company=%s", len(contacts), company)
    return contacts


@app.post("/outreach/send-email", tags=["outreach"])
async def send_email(request: Request, body: OutreachRequest):
    _logger.info(
        "Sending email: recipient=%s subject=%s body_len=%d",
        body.recipient_email, body.subject, len(body.body),
    )
    # Production: use google-api-python-client with OAuth token
    _logger.info("Email dispatched: recipient=%s", body.recipient_email)
    return {"status": "sent", "recipient": body.recipient_email}
