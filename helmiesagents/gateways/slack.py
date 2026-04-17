from __future__ import annotations

from helmiesagents.gateways.base import GatewayAdapter


class SlackAdapter(GatewayAdapter):
    name = "slack"

    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token

    def send_message(self, channel_id: str, text: str) -> None:
        # Intentionally lightweight placeholder to keep core dependency-free.
        # Use Slack SDK integration in next phase for production delivery.
        if not self.bot_token:
            raise RuntimeError("Slack token missing")
        raise NotImplementedError("Slack send integration planned in Phase 2")

    def poll(self):
        return []
