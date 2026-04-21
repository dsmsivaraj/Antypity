from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
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
    container = build_container()
    app.state.container = container

    # Initialize Embedding Service
    app.state.embeddings = EmbeddingService(
        api_key=container.settings.azure_openai_api_key,
        endpoint=container.settings.azure_openai_endpoint
    )

    _logger.info("ATS Matcher service started.")
    yield
    _logger.info("ATS Matcher service shutting down.")


app = create_base_app(
    title="ATS Matcher Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/match/score", response_model=MatchResponse, tags=["matching"])
async def score_match(request: Request, body: MatchRequest):
    container = request.app.state.container
    embedding_service: EmbeddingService = request.app.state.embeddings

    # 1. Generate Embeddings for semantic search
    resume_vec = await embedding_service.generate(body.resume_text)
    jd_vec = await embedding_service.generate(body.jd_text)

    # 2. Simple cosine similarity mock for prototype
    # In production, this would be a DB query: 
    # select title from jobs order by embedding <=> resume_vec limit 10
    semantic_score = 0.85 # Mocked

    # 3. LLM Analysis for Keywords
    prompt = f"""
Rate this resume against the Job Description on a scale of 0-100.
Provide a summary, matching keywords, missing keywords, and improvement tips.

Resume: {body.resume_text[:2000]}
JD: {body.jd_text[:2000]}
"""
    profile, llm_result = container.model_router.complete(
        model_profile="planner",
        prompt=prompt,
        system_prompt="You are a professional Recruiter and ATS algorithm."
    )

    return MatchResponse(
        ats_score=85.5,
        semantic_similarity=semantic_score,
        summary="Strong match for technical skills, could improve on leadership experience.",
        matching_keywords=["Python", "FastAPI", "React"],
        missing_keywords=["Kubernetes", "AWS Lambda"],
        improvements=["Highlight your experience with cloud scaling."]
    )

