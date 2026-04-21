"""ChatbotAgent — multi-turn AI chatbot for resume, job, and career queries.

Maintains conversation history per session. Uses Ollama (Llama) for local
inference with Azure OpenAI as fallback.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from shared.base_agent import AgentMetadata, AgentResult, BaseAgent

_SYSTEM_PROMPT = """You are Antypity Career Coach — an expert career advisor and resume consultant.
You help users with:
- Resume writing, optimization, and ATS improvements
- Job description analysis and matching
- Career advice and interview preparation
- Resume template selection (Figma community library)
- Salary negotiation and job market insights

Be concise, practical, and specific. When discussing resumes or job descriptions,
reference the context provided. If the user asks about templates, explain the
styles available (minimal, modern, executive, academic, data science).

Always be encouraging and constructive."""


class ChatbotAgent(BaseAgent):
    """Multi-turn chatbot with resume/JD context awareness."""

    def __init__(self, ollama_client, llm_client, chat_store) -> None:
        super().__init__(
            metadata=AgentMetadata(
                name="career-chatbot",
                description="AI career coach chatbot. Ask about resumes, job descriptions, templates, career advice, and interview preparation.",
                capabilities=["chatbot", "career advice", "resume help", "interview prep", "job search guidance"],
                preferred_model="ollama-llama3",
            )
        )
        self._ollama = ollama_client
        self._llm = llm_client
        self._store = chat_store

    def can_handle(self, task: str, context: Optional[Dict] = None) -> int:
        t = task.lower()
        if any(kw in t for kw in ("chat", "ask", "help me", "career", "interview", "salary", "negotiate", "advice", "question")):
            return 70
        return 20  # Moderate catch-all for conversational queries

    def execute(self, task: str, context: Optional[Dict] = None) -> AgentResult:
        ctx = context or {}
        session_id = ctx.get("session_id", "default")
        resume_context = ctx.get("resume_text", "")
        jd_context = ctx.get("jd_text", "")

        # Update session context if new resume/JD provided
        if resume_context:
            self._store.update_context(session_id, resume_text=resume_context)
        if jd_context:
            self._store.update_context(session_id, jd_text=jd_context)

        # Build conversation history for the LLM
        session = self._store.get_or_create(session_id)
        history = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in session.get("messages", [])[-10:]  # last 10 turns
        ]

        # Augment system prompt with context
        system = _SYSTEM_PROMPT
        sess_ctx = session.get("context", {})
        if sess_ctx.get("resume_text"):
            system += f"\n\nUser's current resume (excerpt):\n{sess_ctx['resume_text'][:1500]}"
        if sess_ctx.get("jd_text"):
            system += f"\n\nCurrent job description (excerpt):\n{sess_ctx['jd_text'][:1000]}"

        # Try Ollama first, fall back to Azure OpenAI
        result = self._ollama.complete(task, system_prompt=system, history=history)
        if not result.used_llm:
            result = self._llm.complete(task, system_prompt=system)

        response_content = result.content

        # Save messages to session
        self._store.add_message(session_id, role="user", content=task)
        self._store.add_message(session_id, role="assistant", content=response_content)

        return AgentResult(
            output=response_content,
            used_llm=result.used_llm,
            metadata={
                "session_id": session_id,
                "provider": result.provider,
                "turn": len(session.get("messages", [])) // 2 + 1,
            },
        )


class ChatStore:
    """In-memory conversation session store with context tracking."""

    def __init__(self) -> None:
        import threading
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_or_create(self, session_id: str) -> Dict[str, Any]:
        with self._lock:
            if session_id not in self._sessions:
                from datetime import datetime, timezone
                self._sessions[session_id] = {
                    "session_id": session_id,
                    "messages": [],
                    "context": {},
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
            return self._sessions[session_id]

    def add_message(self, session_id: str, role: str, content: str) -> None:
        from datetime import datetime, timezone
        with self._lock:
            session = self._sessions.setdefault(session_id, {
                "session_id": session_id,
                "messages": [],
                "context": {},
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            })
            now = datetime.now(timezone.utc).isoformat()
            session["messages"].append({
                "role": role,
                "content": content,
                "timestamp": now,
            })
            session["updated_at"] = now

    def update_context(self, session_id: str, **kwargs: Any) -> None:
        with self._lock:
            session = self._sessions.setdefault(session_id, {
                "session_id": session_id,
                "messages": [],
                "context": {},
                "created_at": "",
                "updated_at": "",
            })
            session["context"].update(kwargs)

    def get_history(self, session_id: str) -> List[Dict[str, Any]]:
        session = self.get_or_create(session_id)
        return session.get("messages", [])

    def clear(self, session_id: str) -> None:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["messages"] = []

    def list_sessions(self) -> List[str]:
        with self._lock:
            return list(self._sessions.keys())
