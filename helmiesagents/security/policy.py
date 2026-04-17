from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass


@dataclass
class PolicyDecision:
    requires_approval: bool
    reason: str | None = None


class PolicyEngine:
    def __init__(self) -> None:
        self.shell_deny = [r"rm\s+-rf\s+/", r":\(\)\{", r"mkfs", r"shutdown", r"reboot"]
        self.shell_approval = [r"sudo", r"docker", r"apt", r"npm\s+install", r"pip\s+install"]

    def action_hash(self, tool: str, args: dict) -> str:
        payload = json.dumps({"tool": tool, "args": args}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def evaluate(self, tool: str, args: dict) -> PolicyDecision:
        if tool == "run_shell":
            cmd = str(args.get("command", ""))
            for d in self.shell_deny:
                if re.search(d, cmd):
                    return PolicyDecision(True, f"Blocked dangerous command pattern: {d}")
            for a in self.shell_approval:
                if re.search(a, cmd):
                    return PolicyDecision(True, f"Requires approval for sensitive command: {a}")

        if tool in {"write_file"}:
            path = str(args.get("path", ""))
            if path.startswith("/") and not path.startswith("/tmp"):
                return PolicyDecision(True, "Writing absolute paths requires approval")

        return PolicyDecision(False, None)
