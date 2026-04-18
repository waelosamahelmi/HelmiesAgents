from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext


@dataclass
class BenchmarkScenario:
    name: str
    prompt: str
    must_contain: list[str]


@dataclass
class BenchmarkSuite:
    name: str
    description: str
    scenarios: list[BenchmarkScenario]
    pass_threshold: float | None = None


@dataclass
class BenchmarkSummary:
    suite_name: str
    total: int
    passed: int
    score: float
    details: list[dict[str, Any]]
    threshold: float | None = None
    gate_passed: bool | None = None


class BenchmarkHarness:
    def __init__(self, agent: HelmiesAgent, memory: MemoryStore) -> None:
        self.agent = agent
        self.memory = memory

    def run_suite(
        self,
        ctx: RequestContext,
        suite_name: str,
        scenarios: list[BenchmarkScenario],
        *,
        threshold: float | None = None,
    ) -> BenchmarkSummary:
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
                "quality": resp.quality,
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
        gate_passed = score >= threshold if threshold is not None else None
        return BenchmarkSummary(
            suite_name=suite_name,
            total=total,
            passed=passed,
            score=score,
            details=details,
            threshold=threshold,
            gate_passed=gate_passed,
        )

    def load_suites(self, suites_file: str) -> list[BenchmarkSuite]:
        raw = yaml.safe_load(Path(suites_file).read_text()) or {}
        suites: list[BenchmarkSuite] = []
        for s in raw.get("suites", []):
            scenarios = [
                BenchmarkScenario(
                    name=str(item.get("name", "scenario")),
                    prompt=str(item.get("prompt", "")),
                    must_contain=list(item.get("must_contain", [])),
                )
                for item in s.get("scenarios", [])
            ]
            suites.append(
                BenchmarkSuite(
                    name=str(s.get("name", "default")),
                    description=str(s.get("description", "")),
                    scenarios=scenarios,
                    pass_threshold=float(s["pass_threshold"]) if s.get("pass_threshold") is not None else None,
                )
            )
        return suites

    def list_suites(self, suites_file: str) -> list[dict[str, Any]]:
        return [
            {
                "name": s.name,
                "description": s.description,
                "scenario_count": len(s.scenarios),
                "pass_threshold": s.pass_threshold,
            }
            for s in self.load_suites(suites_file)
        ]

    def run_named_suite(
        self,
        ctx: RequestContext,
        *,
        suite_name: str,
        suites_file: str,
        min_score_override: float | None = None,
    ) -> BenchmarkSummary:
        suites = self.load_suites(suites_file)
        suite = next((s for s in suites if s.name == suite_name), None)
        if not suite:
            available = ", ".join(sorted(s.name for s in suites)) or "<none>"
            raise ValueError(f"Unknown benchmark suite: {suite_name}. Available: {available}")

        threshold = min_score_override if min_score_override is not None else suite.pass_threshold
        return self.run_suite(ctx, suite_name=suite.name, scenarios=suite.scenarios, threshold=threshold)
