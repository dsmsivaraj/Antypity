from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from .config import Settings
from .llm_client import LLMResult

_logger = logging.getLogger(__name__)

try:
    from llama_cpp import Llama
except Exception:
    Llama = None


@dataclass(frozen=True)
class LlamaModelConfig:
    profile: str
    path: str


class LocalLlamaClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._models: Dict[str, object] = {}
        self._errors: Dict[str, str] = {}

    @property
    def enabled(self) -> bool:
        return self.settings.llama_enabled and Llama is not None

    @property
    def availability_detail(self) -> str:
        if not self.settings.llama_enabled:
            return "Local LLaMA not configured."
        if Llama is None:
            return "llama-cpp-python not installed."
        return "ok"

    def complete(
        self,
        *,
        prompt: str,
        system_prompt: Optional[str] = None,
        profile: str,
        model_path: Optional[str],
    ) -> LLMResult:
        if not model_path:
            return LLMResult(
                content=self._fallback(prompt, reason="No local model path configured."),
                used_llm=False,
                provider="llama-fallback",
            )
        if Llama is None:
            return LLMResult(
                content=self._fallback(prompt, reason="llama-cpp-python is not installed."),
                used_llm=False,
                provider="llama-fallback",
            )

        model = self._load_model(profile=profile, model_path=model_path)
        if model is None:
            return LLMResult(
                content=self._fallback(prompt, reason=self._errors.get(profile, "Unable to load model.")),
                used_llm=False,
                provider="llama-fallback",
            )

        final_prompt = prompt.strip()
        if system_prompt:
            final_prompt = f"[SYSTEM]\n{system_prompt.strip()}\n\n[USER]\n{final_prompt}\n\n[ASSISTANT]\n"

        try:
            response = model(
                final_prompt,
                max_tokens=self.settings.max_tokens,
                temperature=self.settings.llama_temperature,
                stop=["[USER]", "</s>"],
            )
            content = response["choices"][0]["text"].strip()
            return LLMResult(
                content=content or self._fallback(prompt, reason="Model returned empty output."),
                used_llm=bool(content),
                provider="llama-cpp",
            )
        except Exception as exc:
            _logger.error("Local LLaMA inference failed for profile '%s': %s", profile, exc)
            return LLMResult(
                content=self._fallback(prompt, reason=str(exc)),
                used_llm=False,
                provider="llama-fallback",
            )

    def _load_model(self, *, profile: str, model_path: str):
        if profile in self._models:
            return self._models[profile]
        try:
            model = Llama(model_path=model_path, n_ctx=self.settings.llama_n_ctx, verbose=False)
            self._models[profile] = model
            return model
        except Exception as exc:
            self._errors[profile] = str(exc)
            _logger.error("Failed to load local LLaMA model '%s' from '%s': %s", profile, model_path, exc)
            return None

    def _fallback(self, prompt: str, reason: str) -> str:
        return (
            "Local LLaMA response unavailable. Deterministic fallback returned instead.\n\n"
            f"Reason: {reason}\n\n"
            f"Prompt summary:\n{prompt.strip()}"
        )
