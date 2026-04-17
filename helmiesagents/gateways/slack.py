from __future__ import annotations

import httpx

from helmiesagents.gateways.base import GatewayAdapter


class SlackAdapter(GatewayAdapter):
    name = "slack"

    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token

    def send_message(self, channel_id: str, text: str) -> dict:
        if not self.bot_token:
            raise RuntimeError("Slack token missing")

        with httpx.Client(timeout=20) as client:
            res = client.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {self.bot_token}"},
                json={"channel": channel_id, "text": text},
            )
        data = res.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack error: {data}")
        return {"ok": True, "channel": channel_id, "ts": data.get("ts")}
