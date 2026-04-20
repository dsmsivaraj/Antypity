from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .config import Settings
from .llm_client import LLMClient, LLMResult


@dataclass(frozen=True)
class ModelProfile:
    id: str
    provider: str
    deployment: Optional[str]
    mode: str
    description: str


class ModelRouter:
    def __init__(self, settings: Settings, llm_client: LLMClient) -> None:
        self.settings = settings
        self.llm_client = llm_client
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
                mode="fast",
                description="Deterministic fallback profile for lightweight orchestration.",
            ),
            ModelProfile(
                id="fallback-critic",
                provider="fallback",
                deployment=None,
                mode="critic",
                description="Deterministic fallback profile tuned for review-style prompts.",
            ),
        ]

        if not self.settings.llm_enabled:
            return profiles

        profiles.insert(
            0,
            ModelProfile(
                id="azure-general",
                provider="azure-openai",
                deployment=self.settings.azure_openai_deployment,
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
                    mode="critic",
                    description="Azure OpenAI reviewer profile for audit and review tasks.",
                ),
            )

        return profiles
