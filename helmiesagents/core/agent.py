from __future__ import annotations

import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from helmiesagents.config import Settings
from helmiesagents.context.compression import ContextCompressor
from helmiesagents.core.critic import ResponseCritic
from helmiesagents.core.planner import make_plan
from helmiesagents.execution.budget import ExecutionBudgetPolicy
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
    quality: dict[str, Any] | None = None


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
        self.policy = PolicyEngine(policy_file=settings.policy_dsl_file)
        self.compressor = ContextCompressor()
        self.critic = ResponseCritic()
        self.budget_policy = ExecutionBudgetPolicy(settings.execution_budget_file)
        self.router = ModelRouter(default_model=settings.openai_model, policy_file=settings.routing_policy_file)

    @staticmethod
    def _extract_model_hints_from_prompt(user_prompt: str) -> tuple[str | None, str | None]:
        model_name: str | None = None
        base_url: str | None = None

        m_model = re.search(r"^- model:\s*(.+)$", user_prompt, flags=re.MULTILINE)
        if m_model:
            candidate = m_model.group(1).strip()
            if candidate and candidate != "-":
                model_name = candidate

        m_url = re.search(r"^- base_url:\s*(.+)$", user_prompt, flags=re.MULTILINE)
        if m_url:
            candidate = m_url.group(1).strip()
            if candidate and candidate != "-":
                base_url = candidate

        return model_name, base_url

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

    def _resolve_budget(self, ctx: RequestContext) -> dict[str, Any]:
        b = self.budget_policy.resolve(tenant_id=ctx.tenant_id, roles=ctx.roles)
        return {
            "max_tool_calls": b.max_tool_calls,
            "max_subruns": b.max_subruns,
            "max_critic_retries": b.max_critic_retries,
        }

    def get_effective_budget(self, ctx: RequestContext | None = None) -> dict[str, Any]:
        ctx = ctx or RequestContext()
        return self._resolve_budget(ctx)

    def _apply_tools_and_finalize(
        self,
        *,
        session_id: str,
        ctx: RequestContext,
        model_output: str,
        plan: list[str],
        route_policy: str,
        quality: dict[str, Any] | None = None,
        budget: dict[str, Any] | None = None,
    ) -> AgentResponse:
        tools_executed: list[dict[str, Any]] = []
        tool_calls = 0

        def _run_tools(text: str) -> str:
            nonlocal tool_calls
            output_text = text
            for match in TOOL_PATTERN.finditer(text):
                name = match.group("name")

                if budget is not None and budget.get("max_tool_calls") is not None and tool_calls >= int(budget["max_tool_calls"]):
                    output_text += f"\n\n[tool:{name} budget_blocked] max_tool_calls reached"
                    tools_executed.append(
                        {
                            "tool": name,
                            "args": {},
                            "budget_blocked": True,
                            "reason": "max_tool_calls reached",
                        }
                    )
                    continue
                args_text = match.group("args")
                try:
                    args = json.loads(args_text)
                except json.JSONDecodeError:
                    args = {}

                decision = self.policy.evaluate(name, args)
                if decision.blocked:
                    output_text += f"\n\n[tool:{name} denied] {decision.reason}"
                    tools_executed.append(
                        {
                            "tool": name,
                            "args": args,
                            "denied": True,
                            "reason": decision.reason,
                        }
                    )
                    continue

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
                    tool_calls += 1
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
                    "quality": quality,
                    "budget": budget,
                }
            ),
        )

        return AgentResponse(text=final_text, plan=plan, tools_executed=tools_executed, quality=quality)

    def _repair_prompt(self, *, user_message: str, previous_response: str, critic_feedback: str, required_keywords: list[str]) -> str:
        req_line = ", ".join(required_keywords) if required_keywords else "(none)"
        return (
            "Revise your previous answer to improve quality.\n"
            f"Original user request:\n{user_message}\n\n"
            f"Previous response:\n{previous_response}\n\n"
            f"Critic feedback:\n{critic_feedback}\n\n"
            f"Required keywords to include if relevant: {req_line}\n"
            "Return only the improved final answer. Keep it concise and actionable."
        )

    def _generate_with_critic(
        self,
        *,
        system_prompt: str,
        prompt: str,
        user_message: str,
        model_override: str | None,
        budget: dict[str, Any] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        hinted_model, hinted_base_url = self._extract_model_hints_from_prompt(prompt)
        effective_model = hinted_model or model_override

        required = self.critic.required_keywords_from_prompt(user_message)
        attempts: list[dict[str, Any]] = []

        try:
            current = self.provider.generate(
                system_prompt,
                prompt,
                model_override=effective_model,
                base_url_override=hinted_base_url,
            )
        except TypeError:
            current = self.provider.generate(system_prompt, prompt, model_override=effective_model)
        c = self.critic.evaluate(user_message=user_message, response_text=current, required_keywords=required)
        attempts.append({"attempt": 1, "score": c.score, "pass": c.pass_gate, "feedback": c.feedback})

        max_retries = max(0, int(self.settings.critic_max_retries))
        if budget is not None and budget.get("max_critic_retries") is not None:
            max_retries = min(max_retries, int(budget["max_critic_retries"]))
        target = float(self.settings.critic_min_score)

        if self.settings.critic_enabled:
            tries = 0
            while tries < max_retries and (not c.pass_gate or c.score < target):
                tries += 1
                repair = self._repair_prompt(
                    user_message=user_message,
                    previous_response=current,
                    critic_feedback=c.feedback,
                    required_keywords=required,
                )
                try:
                    current = self.provider.generate(
                        system_prompt,
                        repair,
                        model_override=effective_model,
                        base_url_override=hinted_base_url,
                    )
                except TypeError:
                    current = self.provider.generate(system_prompt, repair, model_override=effective_model)
                c = self.critic.evaluate(user_message=user_message, response_text=current, required_keywords=required)
                attempts.append({"attempt": 1 + tries, "score": c.score, "pass": c.pass_gate, "feedback": c.feedback})

        quality = {
            "enabled": bool(self.settings.critic_enabled),
            "required_keywords": required,
            "attempts": attempts,
            "final_score": c.score,
            "final_pass": bool(c.pass_gate and c.score >= target),
            "target": target,
            "model_used": effective_model,
            "base_url_used": hinted_base_url,
        }
        return current, quality

    def _subrun_prompt(self, *, user_message: str, subtask: str) -> str:
        return (
            "Investigate subtask and return concise findings.\n"
            f"Original request: {user_message}\n"
            f"Subtask: {subtask}\n"
            "Return only findings relevant to this subtask."
        )

    def _detect_subtasks(self, user_message: str, plan: list[str]) -> list[str]:
        text = user_message.strip()
        lower = text.lower()
        parts = []

        # simple decomposition heuristics
        if " and " in lower:
            parts.extend([p.strip() for p in re.split(r"\band\b", text, flags=re.IGNORECASE) if p.strip()])
        if "," in text:
            parts.extend([p.strip() for p in text.split(",") if p.strip()])

        # fallback decomposition only for complex prompts
        complex_cues = ("analyze", "research", "compare", "strategy", "build", "design", "plan")
        if not parts and any(c in lower for c in complex_cues):
            derived = [p for p in plan if p and p.lower().startswith(("collect", "identify", "execute", "validate", "generate"))]
            parts.extend(derived[:2])

        # dedupe, trim, cap
        out: list[str] = []
        seen: set[str] = set()
        for p in parts:
            k = p.lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(p)
        return out[: max(0, int(self.settings.autonomous_subruns_max))]

    def _run_autonomous_subruns(
        self,
        *,
        session_id: str,
        user_message: str,
        plan: list[str],
        system_prompt: str,
        model_override: str | None,
        budget: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        enabled = bool(self.settings.autonomous_subruns_enabled)
        result: dict[str, Any] = {
            "enabled": enabled,
            "subruns_executed": 0,
            "subruns": [],
            "verify_enabled": bool(self.settings.autonomous_subruns_verify),
        }
        if not enabled:
            return result

        subtasks = self._detect_subtasks(user_message, plan)
        if budget is not None and budget.get("max_subruns") is not None:
            subtasks = subtasks[: max(0, int(budget["max_subruns"]))]

        if not subtasks:
            return result

        for idx, subtask in enumerate(subtasks, start=1):
            p = self._subrun_prompt(user_message=user_message, subtask=subtask)
            hinted_model, hinted_base_url = self._extract_model_hints_from_prompt(p)
            effective_model = hinted_model or model_override
            try:
                sub_response = self.provider.generate(
                    system_prompt,
                    p,
                    model_override=effective_model,
                    base_url_override=hinted_base_url,
                )
            except TypeError:
                sub_response = self.provider.generate(system_prompt, p, model_override=effective_model)

            verification: dict[str, Any] | None = None
            if self.settings.autonomous_subruns_verify:
                verify_keywords = self.critic.required_keywords_from_prompt(subtask)
                c = self.critic.evaluate(user_message=subtask, response_text=sub_response, required_keywords=verify_keywords)
                verification = {
                    "score": c.score,
                    "pass": c.pass_gate,
                    "feedback": c.feedback,
                    "required_keywords": verify_keywords,
                }

            result["subruns"].append(
                {
                    "index": idx,
                    "subtask": subtask,
                    "result_preview": sub_response[:400],
                    "verification": verification,
                }
            )

        result["subruns_executed"] = len(result["subruns"])
        return result

    def chat(self, session_id: str, user_message: str, ctx: RequestContext | None = None) -> AgentResponse:
        ctx = ctx or RequestContext()
        plan, prompt, route = self._build_chat_prompt(session_id=session_id, user_message=user_message, ctx=ctx)
        budget = self._resolve_budget(ctx)

        autonomy = self._run_autonomous_subruns(
            session_id=session_id,
            user_message=user_message,
            plan=plan,
            system_prompt=self._system_prompt(),
            model_override=route.model,
            budget=budget,
        )

        if autonomy["subruns"]:
            subrun_block = "\n\nSubrun findings:\n" + "\n".join(
                [f"- [{s['index']}] {s['subtask']}: {s['result_preview']}" for s in autonomy["subruns"]]
            )
            prompt = prompt + subrun_block

        model_output, quality = self._generate_with_critic(
            system_prompt=self._system_prompt(),
            prompt=prompt,
            user_message=user_message,
            model_override=route.model,
            budget=budget,
        )
        quality["autonomy"] = autonomy
        quality["budget"] = budget
        return self._apply_tools_and_finalize(
            session_id=session_id,
            ctx=ctx,
            model_output=model_output,
            plan=plan,
            route_policy=route.policy_name,
            quality=quality,
            budget=budget,
        )

    def stream_chat(self, session_id: str, user_message: str, ctx: RequestContext | None = None) -> Iterable[StreamEvent]:
        ctx = ctx or RequestContext()
        plan, prompt, route = self._build_chat_prompt(session_id=session_id, user_message=user_message, ctx=ctx)
        budget = self._resolve_budget(ctx)

        yield StreamEvent(type="meta", data={"plan": plan, "route_policy": route.policy_name, "model": route.model, "budget": budget})

        chunks: list[str] = []
        hinted_model, hinted_base_url = self._extract_model_hints_from_prompt(prompt)
        effective_model = hinted_model or route.model
        try:
            _stream = self.provider.stream_generate(
                self._system_prompt(),
                prompt,
                model_override=effective_model,
                base_url_override=hinted_base_url,
            )
        except TypeError:
            _stream = self.provider.stream_generate(self._system_prompt(), prompt, model_override=effective_model)
        for chunk in _stream:
            if not chunk:
                continue
            chunks.append(chunk)
            yield StreamEvent(type="token", data={"text": chunk})

        full_text = "".join(chunks)
        autonomy = self._run_autonomous_subruns(
            session_id=session_id,
            user_message=user_message,
            plan=plan,
            system_prompt=self._system_prompt(),
            model_override=route.model,
            budget=budget,
        )
        quality = {
            "enabled": False,
            "required_keywords": self.critic.required_keywords_from_prompt(user_message),
            "attempts": [],
            "final_score": None,
            "final_pass": None,
            "target": float(self.settings.critic_min_score),
            "mode": "stream_no_repair",
            "autonomy": autonomy,
            "budget": budget,
            "model_used": effective_model,
            "base_url_used": hinted_base_url,
        }
        yield StreamEvent(type="model_output", data={"text": full_text})

        final = self._apply_tools_and_finalize(
            session_id=session_id,
            ctx=ctx,
            model_output=full_text,
            plan=plan,
            route_policy=route.policy_name,
            quality=quality,
            budget=budget,
        )
        yield StreamEvent(
            type="final",
            data={
                "response": final.text,
                "plan": final.plan,
                "tools_executed": final.tools_executed,
                "quality": final.quality,
                "tenant_id": ctx.tenant_id,
            },
        )
