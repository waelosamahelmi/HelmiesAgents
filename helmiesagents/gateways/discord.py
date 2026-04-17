from __future__ import annotations

import httpx

from helmiesagents.gateways.base import GatewayAdapter


class DiscordAdapter(GatewayAdapter):
    name = "discord"

    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token

    def send_message(self, channel_id: str, text: str) -> dict:
        if not self.bot_token:
            raise RuntimeError("Discord token missing")

        url = f"https://discord.com/api/v10/channels/{channel_id}/messages"
        with httpx.Client(timeout=20) as client:
            res = client.post(
                url,
                headers={
                    "Authorization": f"Bot {self.bot_token}",
                    "Content-Type": "application/json",
                },
                json={"content": text},
            )
        if res.status_code >= 300:
            raise RuntimeError(f"Discord error: {res.status_code} {res.text[:200]}")
        data = res.json()
        return {"ok": True, "channel_id": channel_id, "message_id": data.get("id")}
