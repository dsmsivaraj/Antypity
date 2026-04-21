from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from io import BytesIO
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
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
    container = build_container()
    app.state.container = container
    _logger.info("Resume Processor service started.")
    yield
    _logger.info("Resume Processor service shutting down.")


app = create_base_app(
    title="Resume Processor Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/resume/parse", tags=["resume"])
async def parse_resume(request: Request, file: UploadFile = File(...)):
    content = await file.read()
    filename = file.filename or "resume.pdf"
    
    text = ""
    if filename.endswith(".pdf"):
        import pypdf
        reader = pypdf.PdfReader(BytesIO(content))
        for page in reader.pages:
            text += page.extract_text()
    elif filename.endswith(".docx"):
        import docx
        doc = docx.Document(BytesIO(content))
        text = "\n".join([para.text for para in doc.paragraphs])
    else:
        raise HTTPException(status_code=400, detail="Unsupported file format.")
        
    return {"text": text, "filename": filename}


@app.post("/resume/analyze", response_model=ResumeAnalysisResponse, tags=["resume"])
async def analyze_resume(request: Request, body: Dict[str, str]):
    text = body.get("text", "")
    jd_text = body.get("jd_text", "")
    
    container = request.app.state.container

    # Delegate to CareerService for analysis (keeps behavior consistent)
    # Note: source_filename is optional here
    record = container.career_service.analyze_resume(
        resume_text=text,
        jd_text=jd_text,
        model_profile=None,
        source_filename=None,
        created_by=None,
    )

    # Attach retrieval-backed evidence to metadata
    try:
        from backend.retrieval import get_context_blocks
        query = (text or "") + "\n" + (jd_text or "")
        contexts = get_context_blocks(query, top_k=5)
        avg_score = sum(c.get('score', 0.0) for c in contexts) / (len(contexts) or 1)
    except Exception:
        contexts = []
        avg_score = 0.0

    metadata = {
        'model_profile': record.get('model_profile'),
        'match_score': record.get('match_score'),
        'provider': record.get('provider'),
        'evidence': contexts,
        'confidence': float(record.get('match_score') or avg_score)
    }

    resp = ResumeAnalysisResponse(
        text=record.get('resume_text', text),
        metadata=metadata,
        suggestions=record.get('suggestions', []),
        ats_keywords=record.get('ats_keywords', []),
    )

    return resp


@app.post('/resume/cover-letter', tags=['resume'])
async def generate_cover_letter(request: Request, body: Dict[str, str]):
    text = body.get('text', '')
    jd_text = body.get('jd_text', '')
    target_role = body.get('target_role', '')
    company = body.get('company_name', '')
    manager = body.get('hiring_manager_name', '')
    tone = body.get('tone', 'professional')

    container = request.app.state.container
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

    # Attach retrieval evidence
    try:
        from backend.retrieval import get_context_blocks
        contexts = get_context_blocks((text or "") + "\n" + (jd_text or ""), top_k=5)
    except Exception:
        contexts = []

    # Ensure record is a dict and attach metadata
    if isinstance(record, dict):
        record.setdefault('metadata', {})
        record['metadata']['evidence'] = contexts
    return record


# ── Prompt registry admin endpoints (development-only) ───────────────────────
@app.post('/prompts/register', tags=['prompts'])
async def register_prompt_endpoint(request: Request, body: Dict[str, Any]):
    name = body.get('name')
    text = body.get('text')
    meta = body.get('meta') or {}
    if not name or not text:
        raise HTTPException(status_code=400, detail='name and text are required')
    try:
        from backend.prompt_registry import register_prompt
        payload = register_prompt(name, text, meta)
        return payload
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/prompts/list', tags=['prompts'])
async def list_prompt_versions_endpoint(name: str):
    try:
        from backend.prompt_registry import list_prompt_versions
        return {'name': name, 'versions': list_prompt_versions(name)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get('/prompts/get', tags=['prompts'])
async def get_prompt_endpoint(name: str, version: Optional[str] = None):
    try:
        from backend.prompt_registry import get_prompt
        return get_prompt(name, version)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail='Prompt or version not found')
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
