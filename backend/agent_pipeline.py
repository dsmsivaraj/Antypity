"""Typed multi-agent pipeline for document-grounded generation.

Pipeline stages:
  SecurityAgent → RetrievalAgent → ReasoningAgent → GenerationAgent

Each stage produces an AgentMessage. The pipeline is optional — if the model
router can satisfy the request directly, the pipeline is bypassed.
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)


class AgentState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class AgentMessage:
    stage: str
    state: AgentState
    payload: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    latency_ms: float = 0.0


# ── Pipeline Stages ────────────────────────────────────────────────────────────

class SecurityStage:
    """Validates input: PII detection, prompt injection guard, length check."""

    MAX_INPUT_CHARS = 20_000

    def run(self, query: str, context: Dict[str, Any]) -> AgentMessage:
        t0 = time.monotonic()
        try:
            if len(query) > self.MAX_INPUT_CHARS:
                return AgentMessage(
                    stage="security",
                    state=AgentState.FAILED,
                    error=f"Input exceeds {self.MAX_INPUT_CHARS} character limit.",
                    latency_ms=(time.monotonic() - t0) * 1000,
                )

            # Lightweight prompt injection guard
            injection_patterns = ["ignore previous", "disregard all", "system prompt:", "you are now"]
            query_lower = query.lower()
            if any(p in query_lower for p in injection_patterns):
                _logger.warning("SecurityStage: potential prompt injection detected")
                # Don't block, just flag
                context["security_flagged"] = True

            # PII check (non-blocking — just metadata)
            try:
                from .pii_detector import get_pii_detector
                detector = get_pii_detector()
                pii_matches = detector.detect(query)
                if pii_matches:
                    context["pii_detected"] = [m.entity_type for m in pii_matches]
                    _logger.info("SecurityStage: PII detected: %s", context["pii_detected"])
            except Exception:
                pass

            return AgentMessage(
                stage="security",
                state=AgentState.COMPLETED,
                payload={"query": query, "context": context},
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            return AgentMessage(
                stage="security",
                state=AgentState.FAILED,
                error=str(exc),
                latency_ms=(time.monotonic() - t0) * 1000,
            )


class RetrievalStage:
    """Retrieves relevant context using hybrid BM25 + dense search."""

    def __init__(self, top_k: int = 5) -> None:
        self.top_k = top_k

    def run(self, query: str, context: Dict[str, Any]) -> AgentMessage:
        t0 = time.monotonic()
        try:
            from .retrieval import get_context_blocks
            blocks = get_context_blocks(query, top_k=self.top_k)
            return AgentMessage(
                stage="retrieval",
                state=AgentState.COMPLETED,
                payload={
                    "query": query,
                    "context_blocks": blocks,
                    "retrieved_count": len(blocks),
                },
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            _logger.warning("RetrievalStage failed: %s", exc)
            return AgentMessage(
                stage="retrieval",
                state=AgentState.COMPLETED,  # degraded but not fatal
                payload={"query": query, "context_blocks": [], "retrieved_count": 0},
                latency_ms=(time.monotonic() - t0) * 1000,
            )


class ReasoningStage:
    """Grades retrieved context relevance; rewrites query if context is poor."""

    MIN_BLOCKS = 1
    MIN_SCORE = 0.1

    def run(
        self,
        query: str,
        context_blocks: List[Dict],
        context: Dict[str, Any],
    ) -> AgentMessage:
        t0 = time.monotonic()
        try:
            good_blocks = [b for b in context_blocks if (b.get("score") or 0.0) >= self.MIN_SCORE]
            context_quality = "good" if len(good_blocks) >= self.MIN_BLOCKS else "poor"

            rewritten_query = query
            if context_quality == "poor":
                # Simple rewrite: expand abbreviations, add question framing
                rewritten_query = f"Please explain: {query.rstrip('?.')}?"
                _logger.debug("ReasoningStage: rewrote query due to poor context")

            return AgentMessage(
                stage="reasoning",
                state=AgentState.COMPLETED,
                payload={
                    "query": rewritten_query,
                    "original_query": query,
                    "context_blocks": good_blocks or context_blocks,
                    "context_quality": context_quality,
                    "query_rewritten": rewritten_query != query,
                },
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            return AgentMessage(
                stage="reasoning",
                state=AgentState.FAILED,
                error=str(exc),
                latency_ms=(time.monotonic() - t0) * 1000,
            )


class GenerationStage:
    """Generates the final response using the model router."""

    def run(
        self,
        query: str,
        context_blocks: List[Dict],
        model_router,
        model_profile: Optional[str],
        system_prompt: Optional[str] = None,
    ) -> AgentMessage:
        t0 = time.monotonic()
        try:
            context_text = "\n\n".join(
                b.get("text", "") for b in context_blocks if b.get("text")
            )
            augmented_prompt = query
            if context_text:
                augmented_prompt = (
                    f"Context:\n{context_text}\n\n"
                    f"Question: {query}"
                )

            profile, result = model_router.complete(
                model_profile=model_profile,
                prompt=augmented_prompt,
                system_prompt=system_prompt,
            )

            return AgentMessage(
                stage="generation",
                state=AgentState.COMPLETED,
                payload={
                    "response": result.content,
                    "used_llm": result.used_llm,
                    "provider": result.provider,
                    "model_profile": profile.id,
                    "context_used": bool(context_text),
                },
                latency_ms=(time.monotonic() - t0) * 1000,
            )
        except Exception as exc:
            return AgentMessage(
                stage="generation",
                state=AgentState.FAILED,
                error=str(exc),
                latency_ms=(time.monotonic() - t0) * 1000,
            )


# ── Pipeline orchestrator ──────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    query: str
    response: str
    used_llm: bool
    provider: str
    model_profile: str
    stages: List[AgentMessage]
    context_blocks: List[Dict]
    total_latency_ms: float
    pii_detected: List[str] = field(default_factory=list)
    security_flagged: bool = False


def run_rag_pipeline(
    query: str,
    model_router,
    model_profile: Optional[str] = None,
    system_prompt: Optional[str] = None,
    retrieval_top_k: int = 5,
) -> PipelineResult:
    """Run the full RAG pipeline synchronously."""
    t_start = time.monotonic()
    stages: List[AgentMessage] = []
    ctx: Dict[str, Any] = {}

    # Stage 1: Security
    sec = SecurityStage().run(query, ctx)
    stages.append(sec)
    if sec.state == AgentState.FAILED:
        return PipelineResult(
            query=query, response=sec.error or "Request blocked by security check.",
            used_llm=False, provider="security-block", model_profile="",
            stages=stages, context_blocks=[],
            total_latency_ms=(time.monotonic() - t_start) * 1000,
            security_flagged=True,
        )

    # Stage 2: Retrieval
    ret = RetrievalStage(top_k=retrieval_top_k).run(query, ctx)
    stages.append(ret)
    context_blocks = ret.payload.get("context_blocks", [])

    # Stage 3: Reasoning
    reas = ReasoningStage().run(query, context_blocks, ctx)
    stages.append(reas)
    final_query = reas.payload.get("query", query)
    final_blocks = reas.payload.get("context_blocks", context_blocks)

    # Stage 4: Generation
    gen = GenerationStage().run(
        query=final_query,
        context_blocks=final_blocks,
        model_router=model_router,
        model_profile=model_profile,
        system_prompt=system_prompt,
    )
    stages.append(gen)

    if gen.state == AgentState.FAILED:
        response = gen.error or "Generation failed."
        used_llm = False
        provider = "error"
        mp = model_profile or ""
    else:
        response = gen.payload.get("response", "")
        used_llm = gen.payload.get("used_llm", False)
        provider = gen.payload.get("provider", "")
        mp = gen.payload.get("model_profile", model_profile or "")

    return PipelineResult(
        query=query,
        response=response,
        used_llm=used_llm,
        provider=provider,
        model_profile=mp,
        stages=stages,
        context_blocks=final_blocks,
        total_latency_ms=(time.monotonic() - t_start) * 1000,
        pii_detected=ctx.get("pii_detected", []),
        security_flagged=ctx.get("security_flagged", False),
    )
