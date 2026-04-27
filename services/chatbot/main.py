from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app
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
    _logger.info("Career Chatbot Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        _logger.info("Career Chatbot Service started successfully.")
    except Exception:
        _logger.critical("Career Chatbot Service failed to start.", exc_info=True)
        raise
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
    _logger.info(
        "Chat query received: user_id=%s message_len=%d has_context=%s",
        body.user_id, len(body.message), bool(body.context),
    )
    container = request.app.state.container
    prompt = f"User asked: {body.message}\nContext: {body.context}"
    try:
        profile, llm_result = container.model_router.complete(
            model_profile="general",
            prompt=prompt,
            system_prompt=(
                "You are an expert career coach and ATS specialist. "
                "Help the user with resumes, templates, and job portal queries."
            ),
        )
        _logger.info(
            "Chat response generated: user_id=%s used_llm=%s profile=%s",
            body.user_id, llm_result.used_llm, profile,
        )
    except Exception:
        _logger.error(
            "Chat query failed: user_id=%s message_len=%d",
            body.user_id, len(body.message), exc_info=True,
        )
        raise HTTPException(status_code=500, detail="Chat service error.")

    return ChatResponse(
        response=llm_result.content,
        suggestions=[
            "Tell me about resume keywords",
            "Which template is best for tech?",
            "Show me jobs on LinkedIn",
        ],
    )
