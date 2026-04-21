from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

from .config import Settings
from .gemini_client import GeminiClient
from .llama_client import LocalLlamaClient
from .llm_client import LLMClient, LLMResult
from .local_llm import OllamaClient

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelProfile:
    id: str
    provider: str
    deployment: Optional[str]
    model_path: Optional[str]
    mode: str
    description: str


class ModelRouter:
    def __init__(
        self,
        settings: Settings,
        llm_client: LLMClient,
        llama_client: Optional[LocalLlamaClient] = None,
        ollama_client: Optional[OllamaClient] = None,
        gemini_client: Optional[GeminiClient] = None,
    ) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.llama_client = llama_client
        self.ollama_client = ollama_client
        self.gemini_client = gemini_client
        self._profiles = self._build_profiles()

    def list_profiles(self) -> List[ModelProfile]:
        return list(self._profiles)

    def get_profile(self, profile_id: str) -> Optional[ModelProfile]:
        return next((profile for profile in self._profiles if profile.id == profile_id), None)

    def complete(
        self,
        *,
        model_profile: Optional[str],
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> tuple[ModelProfile, LLMResult]:
        requested = self.get_profile(model_profile) if model_profile else None
        profile = requested or self._default_profile()

        if profile.provider == "fallback":
            return profile, self.llm_client.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                deployment=None,
            )

        if profile.provider == "gemini":
            if self.gemini_client is None or not self.gemini_client.enabled:
                _logger.warning("Gemini profile requested but client not available — falling back to Ollama/fallback.")
                fallback = next((p for p in self._profiles if p.provider.startswith("ollama")), self._profiles[-1])
                return self.complete(model_profile=fallback.id, prompt=prompt, system_prompt=system_prompt)
            result = self.gemini_client.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                model=profile.deployment,
            )
            if not result.used_llm:
                # Gemini failed (quota, auth, network) — fall back to Ollama or deterministic
                _logger.warning("Gemini call failed (%s) — falling back to next provider.", result.provider)
                fallback = next(
                    (p for p in self._profiles if p.provider.startswith("ollama") or p.provider == "fallback"),
                    self._profiles[-1],
                )
                return self.complete(model_profile=fallback.id, prompt=prompt, system_prompt=system_prompt)
            return profile, result

        if profile.provider == "llama-cpp":
            if self.llama_client is None:
                return profile, LLMResult(
                    content="Local LLaMA client is not configured.",
                    used_llm=False,
                    provider="llama-fallback",
                )
            return profile, self.llama_client.complete(
                prompt=prompt,
                system_prompt=system_prompt,
                profile=profile.id,
                model_path=profile.model_path,
            )

        if profile.provider.startswith("ollama"):
            if self.ollama_client is None or not self.ollama_client.enabled:
                return profile, LLMResult(
                    content="Ollama is not running. Start Ollama and pull a model to use local inference.",
                    used_llm=False,
                    provider="ollama-fallback",
                )
            return profile, self.ollama_client.complete(prompt=prompt, system_prompt=system_prompt)

        return profile, self.llm_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            deployment=profile.deployment,
        )

    def _default_profile(self) -> ModelProfile:
        # Honour explicit override from DEFAULT_MODEL_PROFILE env var
        configured = self.settings.default_model_profile
        if configured:
            override = self.get_profile(configured)
            if override:
                return override
            _logger.warning("DEFAULT_MODEL_PROFILE=%r not found — falling back to auto-select.", configured)

        # Priority: Gemini > Azure > Ollama > fallback
        for preferred_provider in ("gemini", "azure-openai"):
            p = next((p for p in self._profiles if p.provider == preferred_provider), None)
            if p:
                return p
        return self._profiles[0]

    def _build_profiles(self) -> List[ModelProfile]:
        profiles: List[ModelProfile] = [
            ModelProfile(
                id="fallback-fast",
                provider="fallback",
                deployment=None,
                model_path=None,
                mode="fast",
                description="Deterministic fallback profile for lightweight orchestration.",
            ),
            ModelProfile(
                id="fallback-critic",
                provider="fallback",
                deployment=None,
                model_path=None,
                mode="critic",
                description="Deterministic fallback profile tuned for review-style prompts.",
            ),
        ]

        if self.settings.llama_enabled:
            general_path = self.settings.llama_model_path
            resume_path = self.settings.llama_resume_model_path or general_path
            job_path = self.settings.llama_job_model_path or general_path
            template_path = self.settings.llama_template_model_path or general_path
            for profile_id, path, mode, description in (
                (
                    "llama-local-general",
                    general_path,
                    "local-balanced",
                    "Local LLaMA profile for private offline general reasoning and file processing.",
                ),
                (
                    "llama-local-resume",
                    resume_path,
                    "local-resume",
                    "Local LLaMA profile tuned for resume understanding, ATS analysis, and resume chat.",
                ),
                (
                    "llama-local-jd",
                    job_path,
                    "local-job",
                    "Local LLaMA profile tuned for job-description extraction and role matching.",
                ),
                (
                    "llama-local-template",
                    template_path,
                    "local-design",
                    "Local LLaMA profile for resume template generation and Figma-ready design briefs.",
                ),
            ):
                if path:
                    profiles.insert(
                        0,
                        ModelProfile(
                            id=profile_id,
                            provider="llama-cpp",
                            deployment=None,
                            model_path=path,
                            mode=mode,
                            description=description,
                        ),
                    )

        if self.ollama_client and self.ollama_client.enabled:
            model_name = self.ollama_client.model
            for profile_id, mode, description in (
                (
                    f"ollama-{model_name}",
                    "local-balanced",
                    f"Ollama local model ({model_name}) — private inference, no data leaves this machine.",
                ),
                (
                    "ollama-resume",
                    "local-resume",
                    f"Ollama ({model_name}) tuned for resume analysis and ATS scoring.",
                ),
                (
                    "ollama-chat",
                    "local-chat",
                    f"Ollama ({model_name}) for multi-turn career coaching chat.",
                ),
            ):
                profiles.insert(
                    0,
                    ModelProfile(
                        id=profile_id,
                        provider=f"ollama/{model_name}",
                        deployment=None,
                        model_path=None,
                        mode=mode,
                        description=description,
                    ),
                )

        if self.settings.azure_llm_enabled:
            profiles.insert(
                0,
                ModelProfile(
                    id="azure-general",
                    provider="azure-openai",
                    deployment=self.settings.azure_openai_deployment,
                    model_path=None,
                    mode="balanced",
                    description="Primary Azure OpenAI profile for general reasoning and execution.",
                ),
            )

            if self.settings.azure_openai_planner_deployment:
                profiles.insert(
                    1,
                    ModelProfile(
                        id="azure-planner",
                        provider="azure-openai",
                        deployment=self.settings.azure_openai_planner_deployment,
                        model_path=None,
                        mode="planner",
                        description="Azure OpenAI planner profile for structured planning tasks.",
                    ),
                )

            if self.settings.azure_openai_reviewer_deployment:
                profiles.insert(
                    1,
                    ModelProfile(
                        id="azure-reviewer",
                        provider="azure-openai",
                        deployment=self.settings.azure_openai_reviewer_deployment,
                        model_path=None,
                        mode="critic",
                        description="Azure OpenAI reviewer profile for audit and review tasks.",
                    ),
                )

        # Gemini (highest cloud priority — inserted at index 0 last so it wins)
        if self.gemini_client and self.gemini_client.enabled:
            model = self.gemini_client.model
            for profile_id, deployment, mode, description in (
                (
                    "gemini-flash",
                    "gemini-2.0-flash",
                    "fast",
                    "Google Gemini 2.0 Flash — fast, cost-efficient tasks and quick analysis.",
                ),
                (
                    "gemini-pro",
                    "gemini-2.5-pro-preview-05-06",
                    "pro",
                    "Google Gemini 2.5 Pro — complex multi-step reasoning and long documents.",
                ),
                (
                    "gemini-resume",
                    model,
                    "resume",
                    f"Google Gemini ({model}) — resume analysis, ATS scoring, career coaching.",
                ),
                (
                    "gemini-general",
                    model,
                    "balanced",
                    f"Google Gemini ({model}) — primary cloud LLM for all general reasoning.",
                ),
            ):
                profiles.insert(
                    0,
                    ModelProfile(
                        id=profile_id,
                        provider="gemini",
                        deployment=deployment,
                        model_path=None,
                        mode=mode,
                        description=description,
                    ),
                )

        return profiles
