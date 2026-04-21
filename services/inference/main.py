from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Dict, List, Optional

from fastapi import FastAPI, Request
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app

_logger = logging.getLogger(__name__)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    max_tokens: Optional[int] = 1000
    temperature: Optional[float] = 0.7

@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Local Inference Service (Llama) starting up...")
    # In a real setup, we would load llama-cpp or ollama here.
    yield
    _logger.info("Local Inference Service shutting down.")

app = create_base_app(
    title="Local Inference Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)

@app.post("/v1/chat/completions", tags=["inference"])
async def chat_completions(body: ChatCompletionRequest):
    _logger.info("Local inference requested for model: %s", body.model)
    
    # Simulate Llama-based local processing
    last_message = body.messages[-1].content
    response_content = f"[Llama-3-Local] I processed your request: '{last_message[:50]}...'. This analysis was performed locally."
    
    return {
        "id": "chat-local-123",
        "object": "chat.completion",
        "created": 123456789,
        "model": body.model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": response_content
                },
                "finish_reason": "stop"
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 20,
            "total_tokens": 30
        }
    }
