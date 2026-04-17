from __future__ import annotations

from helmiesagents.gateways.base import GatewayAdapter


class TelegramAdapter(GatewayAdapter):
    name = "telegram"

    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token

    def send_message(self, channel_id: str, text: str) -> None:
        if not self.bot_token:
            raise RuntimeError("Telegram token missing")
        raise NotImplementedError("Telegram send integration planned in Phase 2")

    def poll(self):
        return []
