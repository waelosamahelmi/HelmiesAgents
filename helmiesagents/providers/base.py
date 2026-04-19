from __future__ import annotations

from collections.abc import Iterable
from typing import Protocol


class LLMProvider(Protocol):
    name: str

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> str:
        ...

    def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> Iterable[str]:
        ...
