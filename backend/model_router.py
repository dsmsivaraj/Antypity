from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import Settings
from .llama_client import LocalLlamaClient
from .llm_client import LLMClient, LLMResult


@dataclass(frozen=True)
class ModelProfile:
    id: str
    provider: str
    deployment: Optional[str]
    model_path: Optional[str]
    mode: str
    description: str


class ModelRouter:
    def __init__(self, settings: Settings, llm_client: LLMClient, llama_client: Optional[LocalLlamaClient] = None) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.llama_client = llama_client
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

        return profile, self.llm_client.complete(
            prompt=prompt,
            system_prompt=system_prompt,
            deployment=profile.deployment,
        )

    def _default_profile(self) -> ModelProfile:
        azure_profile = next((profile for profile in self._profiles if profile.provider == "azure-openai"), None)
        return azure_profile or self._profiles[0]

    def _build_profiles(self) -> List[ModelProfile]:
        profiles = [
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

        if not self.settings.llm_enabled:
            return profiles

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

        return profiles
