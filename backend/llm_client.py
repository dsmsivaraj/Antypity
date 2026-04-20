from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from .config import Settings

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LLMResult:
    content: str
    used_llm: bool
    provider: str


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._client = None
        self._client_error: Optional[str] = None

    @property
    def enabled(self) -> bool:
        return self.settings.llm_enabled

    @property
    def client_error(self) -> Optional[str]:
        return self._client_error

    def complete(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        deployment: Optional[str] = None,
    ) -> LLMResult:
        if not self.enabled:
            return LLMResult(content=self._fallback(prompt), used_llm=False, provider="disabled")

        client = self._get_client()
        if client is None:
            return LLMResult(content=self._fallback(prompt), used_llm=False, provider="fallback")

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        try:
            response = client.chat.completions.create(
                model=deployment or self.settings.azure_openai_deployment,
                messages=messages,
                max_tokens=self.settings.max_tokens,
                timeout=self.settings.request_timeout_seconds,
            )
            content = response.choices[0].message.content or ""
            return LLMResult(content=content, used_llm=True, provider="azure-openai")
        except Exception as exc:
            _logger.error("Azure OpenAI API call failed: %s", exc)
            return LLMResult(
                content=self._fallback(prompt, api_error=str(exc)),
                used_llm=False,
                provider="fallback",
            )

    def _get_client(self):
        if self._client is not None:
            return self._client
        if self._client_error is not None:
            return None
        try:
            from openai import AzureOpenAI

            self._client = AzureOpenAI(
                api_key=self.settings.azure_openai_api_key,
                api_version=self.settings.azure_openai_api_version,
                azure_endpoint=self.settings.azure_openai_endpoint,
            )
            return self._client
        except Exception as exc:
            self._client_error = str(exc)
            _logger.error("Failed to initialise Azure OpenAI client: %s", exc)
            return None

    def _fallback(self, prompt: str, api_error: Optional[str] = None) -> str:
        msg = (
            "LLM response unavailable. The platform baseline is still operational "
            "and returned a deterministic fallback instead.\n\n"
            f"Task summary:\n{prompt.strip()}"
        )
        error = api_error or self._client_error
        if error:
            msg += f"\n\nLLM error: {error}"
        return msg
