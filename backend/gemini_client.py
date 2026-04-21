"""GeminiClient — Google Gemini API integration."""
from __future__ import annotations

import logging
from typing import Optional

import httpx

from .llm_client import LLMResult

_logger = logging.getLogger(__name__)

_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

GEMINI_MODELS = {
    "gemini-2.0-flash": "Fast, efficient — recommended default for all tasks",
    "gemini-2.5-pro-preview-05-06": "Most capable Gemini model — complex reasoning & long context",
    "gemini-1.5-pro": "High-quality reasoning with 1M context window",
    "gemini-1.5-flash": "Balanced speed and quality",
    "gemini-flash-latest": "Always points to the latest flash model",
}


class GeminiClient:
    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        max_tokens: int = 4000,
        timeout: float = 60.0,
    ) -> None:
        self.api_key = api_key.strip() if api_key else ""
        self.model = model or "gemini-2.0-flash"
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.enabled = bool(self.api_key)
        if self.enabled:
            _logger.info("GeminiClient initialised (model=%s).", self.model)
        else:
            _logger.info("GeminiClient disabled — no GEMINI_API_KEY set.")

    # ── Public API ────────────────────────────────────────────────────────────

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> LLMResult:
        if not self.enabled:
            return LLMResult(content="Gemini not configured.", used_llm=False, provider="gemini-disabled")

        target_model = model or self.model
        url = f"{_BASE_URL}/{target_model}:generateContent"

        body: dict = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": self.max_tokens,
                "temperature": 0.7,
            },
        }
        if system_prompt:
            body["system_instruction"] = {"parts": [{"text": system_prompt}]}

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    url,
                    json=body,
                    headers={
                        "X-goog-api-key": self.api_key,
                        "Content-Type": "application/json",
                    },
                )
                resp.raise_for_status()
                data = resp.json()

            candidates = data.get("candidates", [])
            if not candidates:
                raise ValueError("Gemini returned no candidates")
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts).strip()
            if not text:
                raise ValueError("Gemini returned empty text")

            return LLMResult(content=text, used_llm=True, provider=f"gemini/{target_model}")

        except httpx.HTTPStatusError as exc:
            detail = ""
            try:
                detail = exc.response.json().get("error", {}).get("message", "")
            except Exception:
                pass
            _logger.error("Gemini HTTP error %s: %s", exc.response.status_code, detail or exc)
            return LLMResult(
                content=f"Gemini API error ({exc.response.status_code}): {detail or str(exc)}",
                used_llm=False,
                provider="gemini-error",
            )
        except Exception as exc:
            _logger.error("Gemini request failed: %s", exc)
            return LLMResult(
                content=f"Gemini unavailable: {exc}",
                used_llm=False,
                provider="gemini-error",
            )

    def list_models(self) -> list[dict]:
        return [
            {"id": k, "description": v, "provider": "gemini"}
            for k, v in GEMINI_MODELS.items()
        ]
