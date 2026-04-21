from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Request
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
from backend.container import build_container

_logger = logging.getLogger(__name__)

class ChatQuery(BaseModel):
    user_id: str
    message: str
    context: Optional[Dict] = None

class ChatResponse(BaseModel):
    response: str
    suggestions: List[str]

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    _logger.info("Career Chatbot Service started.")
    yield
    _logger.info("Career Chatbot Service shutting down.")

app = create_base_app(
    title="Career Chatbot Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)

@app.post("/chat/query", response_model=ChatResponse, tags=["chat"])
async def career_query(request: Request, body: ChatQuery):
    container = request.app.state.container
    
    # Process message via LLM (can use local-llama or azure)
    prompt = f"User asked: {body.message}\nContext: {body.context}"
    
    profile, llm_result = container.model_router.complete(
        model_profile="general",
        prompt=prompt,
        system_prompt="You are an expert career coach and ATS specialist. Help the user with resumes, templates, and job portal queries."
    )
    
    return ChatResponse(
        response=llm_result.content,
        suggestions=["Tell me about resume keywords", "Which template is best for tech?", "Show me jobs on LinkedIn"]
    )
