from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app
from backend.container import build_container

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ResumeAnalysisResponse(BaseModel):
    text: str
    metadata: Dict[str, Any]
    suggestions: List[str]
    ats_keywords: List[str]


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Resume Processor Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        _logger.info("Resume Processor Service started successfully.")
    except Exception:
        _logger.critical("Resume Processor Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Resume Processor Service shutting down.")


app = create_base_app(
    title="Resume Processor Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/resume/parse", tags=["resume"])
async def parse_resume(request: Request, file: UploadFile = File(...)):
    filename = file.filename or "resume"
    _logger.info("Resume parse request: filename=%s content_type=%s", filename, file.content_type)

    content = await file.read()
    text = ""

    try:
        if filename.endswith(".pdf"):
            import pypdf
            reader = pypdf.PdfReader(BytesIO(content))
            for page in reader.pages:
                text += page.extract_text() or ""
            _logger.info("PDF parsed: filename=%s pages=%d chars=%d", filename, len(reader.pages), len(text))
        elif filename.endswith(".docx"):
            import docx
            doc = docx.Document(BytesIO(content))
            text = "\n".join(para.text for para in doc.paragraphs)
            _logger.info("DOCX parsed: filename=%s chars=%d", filename, len(text))
        else:
            _logger.warning("Unsupported resume format received: %s", filename)
            raise HTTPException(status_code=400, detail="Unsupported file format.")
    except HTTPException:
        raise
    except Exception:
        _logger.error("Failed to parse resume: filename=%s", filename, exc_info=True)
        raise HTTPException(status_code=422, detail="Failed to parse resume file.")

    return {"text": text, "filename": filename}


@app.post("/resume/analyze", response_model=ResumeAnalysisResponse, tags=["resume"])
async def analyze_resume(request: Request, body: Dict[str, str]):
    text = body.get("text", "")
    jd_text = body.get("jd_text", "")
    _logger.info("Resume analysis: text_len=%d jd_len=%d", len(text), len(jd_text))

    container = request.app.state.container

    try:
        record = container.career_service.analyze_resume(
            resume_text=text,
            jd_text=jd_text,
            model_profile=None,
            source_filename=None,
            created_by=None,
        )
        _logger.info(
            "Resume analysis complete: match_score=%s provider=%s",
            record.get("match_score"), record.get("provider"),
        )
    except Exception:
        _logger.error("Resume analysis failed: text_len=%d jd_len=%d", len(text), len(jd_text), exc_info=True)
        raise HTTPException(status_code=500, detail="Resume analysis failed.")

    contexts = []
    avg_score = 0.0
    try:
        from backend.retrieval import get_context_blocks
        query = text + "\n" + jd_text
        contexts = get_context_blocks(query, top_k=5)
        avg_score = sum(c.get("score", 0.0) for c in contexts) / (len(contexts) or 1)
        _logger.debug("Retrieval context: blocks=%d avg_score=%.3f", len(contexts), avg_score)
    except Exception:
        _logger.warning("Retrieval context unavailable — proceeding without evidence.", exc_info=True)

    metadata = {
        "model_profile": record.get("model_profile"),
        "match_score": record.get("match_score"),
        "provider": record.get("provider"),
        "evidence": contexts,
        "confidence": float(record.get("match_score") or avg_score),
    }

    return ResumeAnalysisResponse(
        text=record.get("resume_text", text),
        metadata=metadata,
        suggestions=record.get("suggestions", []),
        ats_keywords=record.get("ats_keywords", []),
    )


@app.post("/resume/cover-letter", tags=["resume"])
async def generate_cover_letter(request: Request, body: Dict[str, str]):
    text = body.get("text", "")
    jd_text = body.get("jd_text", "")
    target_role = body.get("target_role", "")
    company = body.get("company_name", "")
    manager = body.get("hiring_manager_name", "")
    tone = body.get("tone", "professional")

    _logger.info(
        "Cover letter request: role=%s company=%s tone=%s text_len=%d jd_len=%d",
        target_role, company, tone, len(text), len(jd_text),
    )

    container = request.app.state.container

    try:
        record = container.career_service.create_cover_letter(
            resume_text=text,
            jd_text=jd_text,
            target_role=target_role,
            company_name=company,
            hiring_manager_name=manager,
            tone=tone,
            model_profile=None,
            created_by=None,
        )
        _logger.info("Cover letter generated: role=%s company=%s", target_role, company)
    except Exception:
        _logger.error(
            "Cover letter generation failed: role=%s company=%s", target_role, company, exc_info=True
        )
        raise HTTPException(status_code=500, detail="Cover letter generation failed.")

    try:
        from backend.retrieval import get_context_blocks
        contexts = get_context_blocks((text or "") + "\n" + (jd_text or ""), top_k=5)
        _logger.debug("Cover letter retrieval context: blocks=%d", len(contexts))
    except Exception:
        contexts = []
        _logger.warning("Retrieval context unavailable for cover letter.", exc_info=True)

    if isinstance(record, dict):
        record.setdefault("metadata", {})
        record["metadata"]["evidence"] = contexts

    return record


# ── Prompt registry admin endpoints (development-only) ───────────────────────

@app.post("/prompts/register", tags=["prompts"])
async def register_prompt_endpoint(request: Request, body: Dict[str, Any]):
    name = body.get("name")
    text = body.get("text")
    meta = body.get("meta") or {}
    if not name or not text:
        _logger.warning("Prompt register rejected: missing name or text.")
        raise HTTPException(status_code=400, detail="name and text are required")
    _logger.info("Registering prompt: name=%s", name)
    try:
        from backend.prompt_registry import register_prompt
        payload = register_prompt(name, text, meta)
        _logger.info("Prompt registered: name=%s", name)
        return payload
    except Exception:
        _logger.error("Failed to register prompt: name=%s", name, exc_info=True)
        raise HTTPException(status_code=500, detail="Prompt registration failed.")


@app.get("/prompts/list", tags=["prompts"])
async def list_prompt_versions_endpoint(name: str):
    _logger.debug("Listing prompt versions: name=%s", name)
    try:
        from backend.prompt_registry import list_prompt_versions
        versions = list_prompt_versions(name)
        _logger.info("Prompt versions listed: name=%s count=%d", name, len(versions))
        return {"name": name, "versions": versions}
    except Exception:
        _logger.error("Failed to list prompt versions: name=%s", name, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to list prompt versions.")


@app.get("/prompts/get", tags=["prompts"])
async def get_prompt_endpoint(name: str, version: Optional[str] = None):
    _logger.debug("Fetching prompt: name=%s version=%s", name, version)
    try:
        from backend.prompt_registry import get_prompt
        result = get_prompt(name, version)
        _logger.info("Prompt fetched: name=%s version=%s", name, version)
        return result
    except FileNotFoundError:
        _logger.warning("Prompt not found: name=%s version=%s", name, version)
        raise HTTPException(status_code=404, detail="Prompt or version not found")
    except Exception:
        _logger.error("Failed to fetch prompt: name=%s version=%s", name, version, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch prompt.")
