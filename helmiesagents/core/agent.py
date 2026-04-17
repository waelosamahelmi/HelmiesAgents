from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from helmiesagents.config import Settings
from helmiesagents.core.planner import make_plan
from helmiesagents.memory.store import MemoryStore
from helmiesagents.providers.factory import build_provider
from helmiesagents.tools.registry import ToolRegistry


TOOL_PATTERN = re.compile(r"\[\[tool:(?P<name>[a-zA-Z0-9_\-]+)\s*(?P<args>\{.*?\})\]\]", re.DOTALL)


@dataclass
class AgentResponse:
    text: str
    plan: list[str]
    tools_executed: list[dict[str, Any]]


class HelmiesAgent:
    def __init__(self, settings: Settings, memory: MemoryStore, tools: ToolRegistry) -> None:
        self.settings = settings
        self.memory = memory
        self.tools = tools
        self.provider = build_provider(settings)

    def _system_prompt(self) -> str:
        tool_lines = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools.list_tools()])
        return (
            "You are HelmiesAgents, a practical autonomous agent.\n"
            "If a tool is needed, emit it in this exact syntax: [[tool:tool_name {\"key\":\"value\"}]]\n"
            "Only use available tools. Then continue with concise explanation.\n"
            f"Available tools:\n{tool_lines}"
        )

    def chat(self, session_id: str, user_message: str) -> AgentResponse:
        self.memory.add_message(session_id, "user", user_message)

        recent = self.memory.get_recent_messages(session_id, limit=10)
        context = "\n".join([f"{m.role}: {m.content}" for m in recent])
        plan = make_plan(user_message)

        prompt = (
            f"Context:\n{context}\n\n"
            f"User request:\n{user_message}\n\n"
            "Plan:\n- " + "\n- ".join(plan)
        )
        model_output = self.provider.generate(self._system_prompt(), prompt)

        tools_executed: list[dict[str, Any]] = []

        def _run_tools(text: str) -> str:
            output_text = text
            for match in TOOL_PATTERN.finditer(text):
                name = match.group("name")
                args_text = match.group("args")
                try:
                    args = json.loads(args_text)
                except json.JSONDecodeError:
                    args = {}
                try:
                    result = self.tools.execute(name, args)
                    tools_executed.append({"tool": name, "args": args, "result": result})
                    output_text += f"\n\n[tool:{name} result] {json.dumps(result)[:1500]}"
                except Exception as e:
                    tools_executed.append({"tool": name, "args": args, "error": str(e)})
                    output_text += f"\n\n[tool:{name} error] {str(e)}"
            return output_text

        final_text = _run_tools(model_output)

        self.memory.add_message(session_id, "assistant", final_text)
        return AgentResponse(text=final_text, plan=plan, tools_executed=tools_executed)
