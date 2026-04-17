from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext


@dataclass
class BenchmarkScenario:
    name: str
    prompt: str
    must_contain: list[str]


@dataclass
class BenchmarkSummary:
    suite_name: str
    total: int
    passed: int
    score: float
    details: list[dict[str, Any]]


class BenchmarkHarness:
    def __init__(self, agent: HelmiesAgent, memory: MemoryStore) -> None:
        self.agent = agent
        self.memory = memory

    def run_suite(self, ctx: RequestContext, suite_name: str, scenarios: list[BenchmarkScenario]) -> BenchmarkSummary:
        details: list[dict[str, Any]] = []
        passed = 0

        for s in scenarios:
            resp = self.agent.chat(session_id=f"benchmark:{suite_name}:{s.name}", user_message=s.prompt, ctx=ctx)
            ok = all(k.lower() in resp.text.lower() for k in s.must_contain)
            if ok:
                passed += 1
            detail = {
                "scenario": s.name,
                "passed": ok,
                "required": s.must_contain,
                "response_preview": resp.text[:300],
            }
            details.append(detail)
            self.memory.add_benchmark_result(
                tenant_id=ctx.tenant_id,
                suite_name=suite_name,
                scenario_name=s.name,
                passed=ok,
                score=1.0 if ok else 0.0,
                details_json=json.dumps(detail),
            )

        total = len(scenarios)
        score = (passed / total) * 100 if total else 0.0
        return BenchmarkSummary(suite_name=suite_name, total=total, passed=passed, score=score, details=details)
