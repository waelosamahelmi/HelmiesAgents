from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext


@dataclass
class GatewayEvent:
    platform: str
    channel_id: str
    user_id: str
    text: str
    agent_id: int | None = None
    thread_id: str | None = None


class GatewayRouter:
    """Platform-agnostic inbound event router."""

    def __init__(self, agent: HelmiesAgent, memory: MemoryStore) -> None:
        self.agent = agent
        self.memory = memory

    def _inject_hired_agent_persona(self, *, tenant_id: str, event: GatewayEvent, raw_text: str) -> tuple[str, dict[str, Any] | None]:
        if not event.agent_id:
            return raw_text, None

        hired = self.memory.get_workforce_agent(tenant_id, int(event.agent_id))
        if not hired:
            return raw_text, None

        persona_block = (
            f"You are operating as hired workforce agent #{hired.get('id')}\n"
            f"Name: {hired.get('name')}\n"
            f"Job title: {hired.get('job_title')}\n"
            f"Description: {hired.get('description')}\n"
            f"System prompt contract: {hired.get('system_prompt')}\n"
            f"Skills: {', '.join(hired.get('skills', []))}\n"
            "Follow this persona strictly in style, priorities, and expertise boundaries.\n"
            "If asked outside scope, escalate clearly and propose who should own it.\n\n"
            f"User message:\n{raw_text}"
        )
        return persona_block, hired

    def handle_event(self, event: GatewayEvent, ctx: RequestContext | None = None) -> dict[str, Any]:
        ctx = ctx or RequestContext(user_id=event.user_id)
        session_suffix = f":agent:{event.agent_id}" if event.agent_id is not None else ""
        session_id = f"{event.platform}:{event.channel_id}:{event.user_id}{session_suffix}"

        prompt, hired_agent = self._inject_hired_agent_persona(tenant_id=ctx.tenant_id, event=event, raw_text=event.text)

        result = self.agent.chat(session_id=session_id, user_message=prompt, ctx=ctx)

        if hired_agent and event.thread_id:
            self.memory.add_workforce_bus_message(
                tenant_id=ctx.tenant_id,
                thread_id=event.thread_id,
                from_agent_id=hired_agent.get("id"),
                to_agent_id=None,
                message=result.text,
                metadata={
                    "kind": "gateway_response",
                    "platform": event.platform,
                    "channel_id": event.channel_id,
                },
            )

        return {
            "platform": event.platform,
            "channel_id": event.channel_id,
            "user_id": event.user_id,
            "session_id": session_id,
            "response": result.text,
            "plan": result.plan,
            "tools_executed": result.tools_executed,
            "routed_agent_id": hired_agent.get("id") if hired_agent else None,
            "routed_agent_name": hired_agent.get("name") if hired_agent else None,
        }
