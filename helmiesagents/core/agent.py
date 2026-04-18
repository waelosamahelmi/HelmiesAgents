from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from helmiesagents.config import Settings
from helmiesagents.context.compression import ContextCompressor
from helmiesagents.core.planner import make_plan
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.providers.factory import build_provider
from helmiesagents.routing.model_router import ModelRouter
from helmiesagents.security.policy import PolicyEngine
from helmiesagents.tools.registry import ToolRegistry


TOOL_PATTERN = re.compile(r"\[\[tool:(?P<name>[a-zA-Z0-9_\-]+)\s*(?P<args>\{.*?\})\]\]", re.DOTALL)


@dataclass
class AgentResponse:
    text: str
    plan: list[str]
    tools_executed: list[dict[str, Any]]


@dataclass
class StreamEvent:
    type: str
    data: dict[str, Any]


class HelmiesAgent:
    def __init__(self, settings: Settings, memory: MemoryStore, tools: ToolRegistry) -> None:
        self.settings = settings
        self.memory = memory
        self.tools = tools
        self.provider = build_provider(settings)
        self.policy = PolicyEngine()
        self.compressor = ContextCompressor()
        self.router = ModelRouter(default_model=settings.openai_model, policy_file=settings.routing_policy_file)

    def _system_prompt(self) -> str:
        tool_lines = "\n".join([f"- {t['name']}: {t['description']}" for t in self.tools.list_tools()])
        return (
            "You are HelmiesAgents, a practical autonomous agent.\n"
            "If a tool is needed, emit it in this exact syntax: [[tool:tool_name {\"key\":\"value\"}]]\n"
            "Only use available tools. Then continue with concise explanation.\n"
            f"Available tools:\n{tool_lines}"
        )

    def _build_chat_prompt(self, session_id: str, user_message: str, ctx: RequestContext) -> tuple[list[str], str, Any]:
        self.memory.add_message(ctx.tenant_id, ctx.user_id, session_id, "user", user_message)
        recent = self.memory.get_recent_messages(ctx.tenant_id, ctx.user_id, session_id, limit=30)
        msgs = [(m.role, m.content) for m in recent]
        compressed = self.compressor.compress(msgs, keep_last=10)

        plan = make_plan(user_message)
        route = self.router.route(user_message)

        prompt = (
            (compressed.summary + "\n\n" if compressed.summary else "")
            + f"Context:\n{compressed.recent_context}\n\n"
            + f"User request:\n{user_message}\n\n"
            + "Plan:\n- "
            + "\n- ".join(plan)
        )
        return plan, prompt, route

    def _apply_tools_and_finalize(
        self,
        *,
        session_id: str,
        ctx: RequestContext,
        model_output: str,
        plan: list[str],
        route_policy: str,
    ) -> AgentResponse:
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

                decision = self.policy.evaluate(name, args)
                if decision.requires_approval and not (ctx.auto_approve or "admin" in ctx.roles):
                    output_text += f"\n\n[tool:{name} approval_required] {decision.reason}"
                    tools_executed.append(
                        {
                            "tool": name,
                            "args": args,
                            "approval_required": True,
                            "reason": decision.reason,
                        }
                    )
                    continue

                try:
                    result = self.tools.execute(name, args)
                    tools_executed.append({"tool": name, "args": args, "result": result})
                    output_text += f"\n\n[tool:{name} result] {json.dumps(result)[:1500]}"
                except Exception as e:
                    tools_executed.append({"tool": name, "args": args, "error": str(e)})
                    output_text += f"\n\n[tool:{name} error] {str(e)}"
            return output_text

        final_text = _run_tools(model_output)
        self.memory.add_message(ctx.tenant_id, ctx.user_id, session_id, "assistant", final_text)

        self.memory.log_audit(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            event_type="agent_chat",
            payload_json=json.dumps(
                {
                    "session_id": session_id,
                    "route_policy": route_policy,
                    "tools_count": len(tools_executed),
                }
            ),
        )

        return AgentResponse(text=final_text, plan=plan, tools_executed=tools_executed)

    def chat(self, session_id: str, user_message: str, ctx: RequestContext | None = None) -> AgentResponse:
        ctx = ctx or RequestContext()
        plan, prompt, route = self._build_chat_prompt(session_id=session_id, user_message=user_message, ctx=ctx)
        model_output = self.provider.generate(self._system_prompt(), prompt, model_override=route.model)
        return self._apply_tools_and_finalize(
            session_id=session_id,
            ctx=ctx,
            model_output=model_output,
            plan=plan,
            route_policy=route.policy_name,
        )

    def stream_chat(self, session_id: str, user_message: str, ctx: RequestContext | None = None) -> Iterable[StreamEvent]:
        ctx = ctx or RequestContext()
        plan, prompt, route = self._build_chat_prompt(session_id=session_id, user_message=user_message, ctx=ctx)

        yield StreamEvent(type="meta", data={"plan": plan, "route_policy": route.policy_name, "model": route.model})

        chunks: list[str] = []
        for chunk in self.provider.stream_generate(self._system_prompt(), prompt, model_override=route.model):
            if not chunk:
                continue
            chunks.append(chunk)
            yield StreamEvent(type="token", data={"text": chunk})

        full_text = "".join(chunks)
        yield StreamEvent(type="model_output", data={"text": full_text})

        final = self._apply_tools_and_finalize(
            session_id=session_id,
            ctx=ctx,
            model_output=full_text,
            plan=plan,
            route_policy=route.policy_name,
        )
        yield StreamEvent(
            type="final",
            data={
                "response": final.text,
                "plan": final.plan,
                "tools_executed": final.tools_executed,
                "tenant_id": ctx.tenant_id,
            },
        )
