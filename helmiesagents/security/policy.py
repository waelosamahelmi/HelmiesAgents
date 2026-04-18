from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class PolicyDecision:
    requires_approval: bool
    reason: str | None = None
    blocked: bool = False
    effect: str = "allow"  # allow | approve | deny
    rule_name: str | None = None


class PolicyEngine:
    def __init__(self, policy_file: str | None = None) -> None:
        self.shell_deny = [r"rm\s+-rf\s+/", r":\(\)\{", r"mkfs", r"shutdown", r"reboot"]
        self.shell_approval = [r"\bsudo\b", r"\bdocker\b", r"\bapt\b", r"\bnpm\s+install\b", r"\bpip\s+install\b"]
        self.dsl_rules: list[dict[str, Any]] = []

        if policy_file:
            self._load_dsl(policy_file)

    def _load_dsl(self, policy_file: str) -> None:
        try:
            p = Path(policy_file)
            if not p.exists():
                return
            raw = yaml.safe_load(p.read_text()) or {}
            rules = raw.get("rules", [])
            if isinstance(rules, list):
                self.dsl_rules = [r for r in rules if isinstance(r, dict)]
        except Exception:
            # Invalid policy DSL must not crash runtime; fallback to builtin policy only.
            self.dsl_rules = []

    def action_hash(self, tool: str, args: dict) -> str:
        payload = json.dumps({"tool": tool, "args": args}, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()

    def _match_rule(self, rule: dict[str, Any], tool: str, args: dict[str, Any]) -> bool:
        rule_tool = str(rule.get("tool", "*")).strip()
        if rule_tool not in {"*", tool}:
            return False

        when = rule.get("when") or {}
        if not isinstance(when, dict):
            return False

        command_regex = when.get("command_regex")
        if command_regex is not None:
            cmd = str(args.get("command", ""))
            if not re.search(str(command_regex), cmd):
                return False

        path_prefix = when.get("path_prefix")
        if path_prefix is not None:
            path = str(args.get("path", ""))
            if not path.startswith(str(path_prefix)):
                return False

        arg_equals = when.get("arg_equals")
        if arg_equals is not None:
            if not isinstance(arg_equals, dict):
                return False
            for k, v in arg_equals.items():
                if args.get(k) != v:
                    return False

        return True

    def _evaluate_dsl(self, tool: str, args: dict[str, Any]) -> PolicyDecision | None:
        if not self.dsl_rules:
            return None

        matches: list[tuple[int, int, dict[str, Any]]] = []
        # Higher score wins. deny > approve > allow. For ties, first rule keeps priority.
        effect_score = {"allow": 1, "approve": 2, "deny": 3}

        for idx, rule in enumerate(self.dsl_rules):
            if not self._match_rule(rule, tool, args):
                continue
            effect = str(rule.get("effect", "allow")).lower()
            if effect not in effect_score:
                continue
            matches.append((effect_score[effect], -idx, rule))

        if not matches:
            return None

        _, _, winner = max(matches, key=lambda x: (x[0], x[1]))
        effect = str(winner.get("effect", "allow")).lower()
        rule_name = str(winner.get("name", "unnamed-rule"))

        if effect == "deny":
            return PolicyDecision(
                requires_approval=True,
                reason=f"Denied by policy rule: {rule_name}",
                blocked=True,
                effect="deny",
                rule_name=rule_name,
            )

        if effect == "approve":
            return PolicyDecision(
                requires_approval=True,
                reason=f"Requires approval by policy rule: {rule_name}",
                blocked=False,
                effect="approve",
                rule_name=rule_name,
            )

        return PolicyDecision(
            requires_approval=False,
            reason=f"Allowed by policy rule: {rule_name}",
            blocked=False,
            effect="allow",
            rule_name=rule_name,
        )

    def _evaluate_builtin(self, tool: str, args: dict[str, Any]) -> PolicyDecision:
        if tool == "run_shell":
            cmd = str(args.get("command", ""))
            for d in self.shell_deny:
                if re.search(d, cmd):
                    return PolicyDecision(
                        True,
                        f"Blocked dangerous command pattern: {d}",
                        blocked=True,
                        effect="deny",
                        rule_name=f"builtin:{d}",
                    )
            for a in self.shell_approval:
                if re.search(a, cmd):
                    return PolicyDecision(
                        True,
                        f"Requires approval for sensitive command: {a}",
                        blocked=False,
                        effect="approve",
                        rule_name=f"builtin:{a}",
                    )

        if tool in {"write_file"}:
            path = str(args.get("path", ""))
            if path.startswith("/") and not path.startswith("/tmp"):
                return PolicyDecision(
                    True,
                    "Writing absolute paths requires approval",
                    blocked=False,
                    effect="approve",
                    rule_name="builtin:absolute-path-write",
                )

        return PolicyDecision(False, None, blocked=False, effect="allow", rule_name="builtin:default-allow")

    def evaluate(self, tool: str, args: dict) -> PolicyDecision:
        dsl_decision = self._evaluate_dsl(tool, args)
        if dsl_decision is not None:
            return dsl_decision
        return self._evaluate_builtin(tool, args)
