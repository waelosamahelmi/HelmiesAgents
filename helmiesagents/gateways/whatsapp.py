from __future__ import annotations

import httpx

from helmiesagents.gateways.base import GatewayAdapter


class WhatsAppAdapter(GatewayAdapter):
    name = "whatsapp"

    def __init__(self, api_url: str | None = None, token: str | None = None) -> None:
        self.api_url = api_url
        self.token = token

    def send_message(self, channel_id: str, text: str) -> dict:
        if not self.api_url or not self.token:
            raise RuntimeError("WhatsApp credentials missing")

        with httpx.Client(timeout=20) as client:
            res = client.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.token}",
                    "Content-Type": "application/json",
                },
                json={"to": channel_id, "text": text},
            )
        if res.status_code >= 300:
            raise RuntimeError(f"WhatsApp error: {res.status_code} {res.text[:200]}")
        return {"ok": True, "channel_id": channel_id, "status": res.status_code}
