from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.security.policy import PolicyEngine


@dataclass
class ApprovalOutcome:
    approved: bool
    approval_id: int | None = None
    reason: str | None = None


class ApprovalManager:
    def __init__(self, memory: MemoryStore, policy: PolicyEngine) -> None:
        self.memory = memory
        self.policy = policy

    def check_or_create(self, ctx: RequestContext, tool: str, args: dict[str, Any]) -> ApprovalOutcome:
        decision = self.policy.evaluate(tool, args)
        if not decision.requires_approval:
            return ApprovalOutcome(approved=True)

        if ctx.auto_approve or "admin" in ctx.roles:
            return ApprovalOutcome(approved=True, reason="auto-approved by policy context")

        action_hash = self.policy.action_hash(tool, args)
        approval_id = self.memory.add_approval(
            tenant_id=ctx.tenant_id,
            user_id=ctx.user_id,
            action_hash=action_hash,
            tool_name=tool,
            args_json=json.dumps(args),
            reason=decision.reason,
            status="pending",
        )
        return ApprovalOutcome(approved=False, approval_id=approval_id, reason=decision.reason)
