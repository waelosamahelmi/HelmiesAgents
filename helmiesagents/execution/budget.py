from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class ExecutionBudget:
    max_tool_calls: int | None = None
    max_subruns: int | None = None
    max_critic_retries: int | None = None


class ExecutionBudgetPolicy:
    """Role/tenant budget policy loaded from YAML.

    Example:
    version: 1
    defaults:
      max_tool_calls: 10
      max_subruns: 2
      max_critic_retries: 1
    tenants:
      default:
        max_tool_calls: 8
    roles:
      viewer:
        max_tool_calls: 3
        max_subruns: 1
        max_critic_retries: 0
    """

    def __init__(self, policy_file: str | None = None) -> None:
        self.defaults = ExecutionBudget()
        self.tenant_overrides: dict[str, ExecutionBudget] = {}
        self.role_overrides: dict[str, ExecutionBudget] = {}
        if policy_file:
            self._load(policy_file)

    def _parse_budget(self, raw: dict[str, Any] | None) -> ExecutionBudget:
        raw = raw or {}
        return ExecutionBudget(
            max_tool_calls=self._int_or_none(raw.get("max_tool_calls")),
            max_subruns=self._int_or_none(raw.get("max_subruns")),
            max_critic_retries=self._int_or_none(raw.get("max_critic_retries")),
        )

    @staticmethod
    def _int_or_none(v: Any) -> int | None:
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    def _load(self, policy_file: str) -> None:
        try:
            p = Path(policy_file)
            if not p.exists():
                return
            data = yaml.safe_load(p.read_text()) or {}
            self.defaults = self._parse_budget(data.get("defaults"))

            tenants = data.get("tenants") or {}
            if isinstance(tenants, dict):
                for tenant_id, raw in tenants.items():
                    self.tenant_overrides[str(tenant_id)] = self._parse_budget(raw if isinstance(raw, dict) else {})

            roles = data.get("roles") or {}
            if isinstance(roles, dict):
                for role, raw in roles.items():
                    self.role_overrides[str(role)] = self._parse_budget(raw if isinstance(raw, dict) else {})
        except Exception:
            # invalid file should not crash runtime
            self.defaults = ExecutionBudget()
            self.tenant_overrides = {}
            self.role_overrides = {}

    @staticmethod
    def _merge(base: ExecutionBudget, overlay: ExecutionBudget) -> ExecutionBudget:
        return ExecutionBudget(
            max_tool_calls=overlay.max_tool_calls if overlay.max_tool_calls is not None else base.max_tool_calls,
            max_subruns=overlay.max_subruns if overlay.max_subruns is not None else base.max_subruns,
            max_critic_retries=(
                overlay.max_critic_retries if overlay.max_critic_retries is not None else base.max_critic_retries
            ),
        )

    def resolve(self, *, tenant_id: str, roles: list[str]) -> ExecutionBudget:
        out = self.defaults

        t = self.tenant_overrides.get(tenant_id)
        if t is not None:
            out = self._merge(out, t)

        for role in roles:
            r = self.role_overrides.get(role)
            if r is not None:
                out = self._merge(out, r)

        return out
