"""OllamaClient — wraps the local Ollama REST API for Llama model inference.

Ollama must be running locally: `ollama serve`
Pull a model first: `ollama pull llama3`

Falls back gracefully when Ollama is not available.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

from .llm_client import LLMResult

_logger = logging.getLogger(__name__)


class OllamaClient:
    """Thin httpx wrapper around the Ollama local inference server."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "llama3") -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.enabled, self._availability_detail = self._check()

    # ── Public API ────────────────────────────────────────────────────────────

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> LLMResult:
        if not self.enabled:
            return LLMResult(
                content=(
                    f"Local Llama model unavailable ({self._availability_detail}). "
                    "Ensure Ollama is running (`ollama serve`) and the model is pulled "
                    f"(`ollama pull {self.model}`)."
                ),
                used_llm=False,
                provider="ollama-unavailable",
            )

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        try:
            resp = httpx.post(
                f"{self.base_url}/api/chat",
                json={"model": self.model, "messages": messages, "stream": False},
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            content = data.get("message", {}).get("content", "")
            return LLMResult(content=content, used_llm=True, provider=f"ollama/{self.model}")
        except Exception as exc:
            _logger.error("Ollama API call failed: %s", exc)
            return LLMResult(
                content=f"Ollama inference failed: {exc}",
                used_llm=False,
                provider="ollama-error",
            )

    def list_local_models(self) -> List[str]:
        """Return names of models installed in this Ollama instance."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=5.0)
            resp.raise_for_status()
            return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []

    # ── Internal ──────────────────────────────────────────────────────────────

    def _check(self) -> tuple[bool, str]:
        """Probe Ollama and verify the target model is available."""
        try:
            resp = httpx.get(f"{self.base_url}/api/tags", timeout=3.0)
            if resp.status_code != 200:
                return False, f"HTTP {resp.status_code} from Ollama"
            models = resp.json().get("models", [])
            base_names = {m["name"].split(":")[0] for m in models}
            target = self.model.split(":")[0]
            if target not in base_names:
                available = ", ".join(sorted(base_names)) or "none"
                return False, f"model '{self.model}' not pulled (available: {available})"
            return True, "ok"
        except httpx.ConnectError:
            return False, "Ollama not running at " + self.base_url
        except Exception as exc:
            return False, str(exc)
