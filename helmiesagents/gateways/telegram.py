from __future__ import annotations

import httpx

from helmiesagents.gateways.base import GatewayAdapter


class TelegramAdapter(GatewayAdapter):
    name = "telegram"

    def __init__(self, bot_token: str | None = None) -> None:
        self.bot_token = bot_token

    def send_message(self, channel_id: str, text: str) -> dict:
        if not self.bot_token:
            raise RuntimeError("Telegram token missing")

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        with httpx.Client(timeout=20) as client:
            res = client.post(url, json={"chat_id": channel_id, "text": text})
            data = res.json()
        if not data.get("ok"):
            raise RuntimeError(f"Telegram error: {data}")
        return {"ok": True, "chat_id": channel_id, "message_id": data.get("result", {}).get("message_id")}
