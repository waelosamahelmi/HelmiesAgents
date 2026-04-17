from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class RequestContext:
    tenant_id: str = "default"
    user_id: str = "anonymous"
    roles: list[str] = field(default_factory=lambda: ["viewer"])
    auto_approve: bool = False


class CancellationToken:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


def is_admin(ctx: RequestContext) -> bool:
    return "admin" in ctx.roles
