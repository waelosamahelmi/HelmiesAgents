from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from helmiesagents.core.agent import HelmiesAgent


@dataclass
class GatewayEvent:
    platform: str
    channel_id: str
    user_id: str
    text: str


class GatewayRouter:
    """Platform-agnostic inbound event router.

    This enables one gateway behavior across Slack/Telegram/WhatsApp/Discord.
    """

    def __init__(self, agent: HelmiesAgent) -> None:
        self.agent = agent

    def handle_event(self, event: GatewayEvent) -> dict[str, Any]:
        session_id = f"{event.platform}:{event.channel_id}:{event.user_id}"
        result = self.agent.chat(session_id=session_id, user_message=event.text)
        return {
            "platform": event.platform,
            "channel_id": event.channel_id,
            "user_id": event.user_id,
            "session_id": session_id,
            "response": result.text,
            "plan": result.plan,
            "tools_executed": result.tools_executed,
        }
