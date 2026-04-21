from __future__ import annotations

from typing import Any, Dict, Optional

from .llm_client import LLMResult


def normalize_completion(value: Any, default_provider: str = "adapter") -> LLMResult:
    """Normalize different LLM client outputs into an LLMResult.

    Accepts:
    - LLMResult -> returned as-is
    - dict with keys 'content', 'used_llm', 'provider' optionally
    - plain string -> wrapped into LLMResult with used_llm=False
    - None -> empty fallback LLMResult
    """
    if isinstance(value, LLMResult):
        return value
    if value is None:
        return LLMResult(content="", used_llm=False, provider=default_provider, provider_meta=None)
    if isinstance(value, dict):
        content = value.get("content") or value.get("text") or ""
        used = bool(value.get("used_llm", True))
        provider = value.get("provider", default_provider)
        meta = value.get("provider_meta") or value.get("meta") or None
        return LLMResult(content=content, used_llm=used, provider=provider, provider_meta=meta)
    # fallback: assume string
    if isinstance(value, str):
        return LLMResult(content=value, used_llm=False, provider=default_provider, provider_meta=None)
    # unknown type -> stringify
    return LLMResult(content=str(value), used_llm=False, provider=default_provider, provider_meta=None)
