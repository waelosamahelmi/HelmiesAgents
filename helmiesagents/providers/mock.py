from __future__ import annotations

from collections.abc import Iterable


class MockProvider:
    name = "mock"

    def _build_response(self, user_prompt: str) -> str:
        marker = "User request:\n"
        if marker in user_prompt:
            q = user_prompt.split(marker, 1)[1].split("\n\nPlan:", 1)[0].lower()
        else:
            q = user_prompt.lower()

        if "time" in q:
            return "[[tool:time_now {}]]\nThe current time was retrieved using the local tool."
        if "list files" in q or "show files" in q:
            return '[[tool:search_files {"pattern":"*","path":"."}]]\nI listed files in the current workspace.'
        if "ingest" in q and "file" in q:
            return '[[tool:ingest_to_markdown {"path":"README.md"}]]\nFile ingestion done.'
        return (
            "HelmiesAgents processed your request. "
            "If you want tool execution, ask explicitly (e.g., 'what time is it' or 'list files')."
        )

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> str:
        _ = model_override, base_url_override
        return self._build_response(user_prompt)

    def stream_generate(
        self,
        system_prompt: str,
        user_prompt: str,
        model_override: str | None = None,
        base_url_override: str | None = None,
    ) -> Iterable[str]:
        _ = model_override, base_url_override
        text = self._build_response(user_prompt)
        for ch in text:
            yield ch
