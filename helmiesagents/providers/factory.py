from __future__ import annotations

from helmiesagents.config import Settings
from helmiesagents.providers.mock import MockProvider
from helmiesagents.providers.openai_compatible import OpenAICompatibleProvider


def build_provider(settings: Settings):
    if settings.provider in {"openai", "auto"} and settings.openai_api_key:
        return OpenAICompatibleProvider(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_model,
        )
    return MockProvider()
