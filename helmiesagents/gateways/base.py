from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IncomingMessage:
    user_id: str
    channel_id: str
    text: str


class GatewayAdapter:
    name: str = "base"

    def send_message(self, channel_id: str, text: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def poll(self) -> list[IncomingMessage]:  # pragma: no cover
        raise NotImplementedError
