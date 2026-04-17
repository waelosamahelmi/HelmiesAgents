from __future__ import annotations

from helmiesagents.gateways.base import GatewayAdapter


class WhatsAppAdapter(GatewayAdapter):
    name = "whatsapp"

    def __init__(self, api_url: str | None = None, token: str | None = None) -> None:
        self.api_url = api_url
        self.token = token

    def send_message(self, channel_id: str, text: str) -> None:
        if not self.api_url or not self.token:
            raise RuntimeError("WhatsApp credentials missing")
        raise NotImplementedError("WhatsApp send integration planned in Phase 2")

    def poll(self):
        return []
