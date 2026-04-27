from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app
from shared.service_utils.embeddings import EmbeddingService
from backend.container import build_container

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class MatchRequest(BaseModel):
    resume_text: str
    jd_text: str


class MatchResponse(BaseModel):
    ats_score: float
    semantic_similarity: float
    summary: str
    matching_keywords: List[str]
    missing_keywords: List[str]
    improvements: List[str]


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("ATS Matcher Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        app.state.embeddings = EmbeddingService(
            api_key=container.settings.azure_openai_api_key,
            endpoint=container.settings.azure_openai_endpoint,
        )
        _logger.info("ATS Matcher Service started successfully.")
    except Exception:
        _logger.critical("ATS Matcher Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("ATS Matcher Service shutting down.")


app = create_base_app(
    title="ATS Matcher Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/match/score", response_model=MatchResponse, tags=["matching"])
async def score_match(request: Request, body: MatchRequest):
    _logger.info(
        "ATS match request: resume_len=%d jd_len=%d",
        len(body.resume_text), len(body.jd_text),
    )
    container = request.app.state.container
    embedding_service: EmbeddingService = request.app.state.embeddings

    try:
        resume_vec = await embedding_service.generate(body.resume_text)
        jd_vec = await embedding_service.generate(body.jd_text)
        _logger.debug("Embeddings generated for ATS match.")
    except Exception:
        _logger.error("Embedding generation failed for ATS match.", exc_info=True)
        raise HTTPException(status_code=500, detail="Embedding service error.")

    semantic_score = 0.85  # placeholder — replace with real cosine similarity

    prompt = (
        f"Rate this resume against the Job Description on a scale of 0-100.\n"
        f"Provide a summary, matching keywords, missing keywords, and improvement tips.\n\n"
        f"Resume: {body.resume_text[:2000]}\nJD: {body.jd_text[:2000]}"
    )

    try:
        profile, llm_result = container.model_router.complete(
            model_profile="planner",
            prompt=prompt,
            system_prompt="You are a professional Recruiter and ATS algorithm.",
        )
        _logger.info(
            "ATS LLM analysis complete: used_llm=%s profile=%s",
            llm_result.used_llm, profile,
        )
    except Exception:
        _logger.error("LLM analysis failed during ATS match.", exc_info=True)
        raise HTTPException(status_code=500, detail="LLM analysis error.")

    return MatchResponse(
        ats_score=85.5,
        semantic_similarity=semantic_score,
        summary="Strong match for technical skills, could improve on leadership experience.",
        matching_keywords=["Python", "FastAPI", "React"],
        missing_keywords=["Kubernetes", "AWS Lambda"],
        improvements=["Highlight your experience with cloud scaling."],
    )
