from __future__ import annotations


class MockProvider:
    name = "mock"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        # Focus only on user request section to avoid false matches from tool docs.
        marker = "User request:\n"
        if marker in user_prompt:
            q = user_prompt.split(marker, 1)[1].split("\n\nPlan:", 1)[0].lower()
        else:
            q = user_prompt.lower()

        if "time" in q:
            return "[[tool:time_now {}]]\nThe current time was retrieved using the local tool."
        if "list files" in q or "show files" in q:
            return "[[tool:search_files {\"pattern\":\"*\",\"path\":\".\"}]]\nI listed files in the current workspace."
        if "run" in q and "workflow" in q:
            return "I can run a workflow file via CLI/API using the workflow engine."
        return (
            "HelmiesAgents processed your request. "
            "If you want tool execution, ask explicitly (e.g., 'what time is it' or 'list files')."
        )
