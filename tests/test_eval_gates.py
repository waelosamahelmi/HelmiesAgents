from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.benchmark.harness import BenchmarkHarness
from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry


def _build_harness(tmp_path):
    settings = Settings(db_path=str(tmp_path / "evals.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)
    return BenchmarkHarness(agent, memory)


def test_run_named_suite_with_threshold_gate(tmp_path):
    suites_file = tmp_path / "suites.yaml"
    suites_file.write_text(
        yaml.safe_dump(
            {
                "suites": [
                    {
                        "name": "smoke",
                        "description": "basic regressions",
                        "pass_threshold": 90,
                        "scenarios": [
                            {
                                "name": "time",
                                "prompt": "what time is it",
                                "must_contain": ["time"],
                            }
                        ],
                    }
                ]
            }
        )
    )

    harness = _build_harness(tmp_path)
    summary = harness.run_named_suite(
        RequestContext(tenant_id="default", user_id="u1", roles=["admin"]),
        suite_name="smoke",
        suites_file=str(suites_file),
    )

    assert summary.suite_name == "smoke"
    assert summary.total == 1
    assert summary.threshold == 90
    assert summary.gate_passed is True
    assert "quality" in summary.details[0]


def test_api_benchmark_suites_and_gate(tmp_path):
    suites_file = tmp_path / "suites.yaml"
    suites_file.write_text(
        yaml.safe_dump(
            {
                "suites": [
                    {
                        "name": "smoke",
                        "description": "basic regressions",
                        "pass_threshold": 90,
                        "scenarios": [
                            {
                                "name": "files",
                                "prompt": "list files",
                                "must_contain": ["files"],
                            }
                        ],
                    }
                ]
            }
        )
    )

    settings = Settings(db_path=str(tmp_path / "api_evals.db"), eval_suites_file=str(suites_file))
    app = create_app(settings)
    client = TestClient(app)

    listed = client.get("/benchmark/suites")
    assert listed.status_code == 200
    body = listed.json()
    assert any(s["name"] == "smoke" for s in body["suites"])

    gated = client.post("/benchmark/gate", json={"suite_name": "smoke"})
    assert gated.status_code == 200
    gbody = gated.json()
    assert gbody["ok"] is True
    assert gbody["summary"]["suite_name"] == "smoke"


def test_api_benchmark_gate_fails_on_strict_override(tmp_path):
    suites_file = tmp_path / "suites.yaml"
    suites_file.write_text(
        yaml.safe_dump(
            {
                "suites": [
                    {
                        "name": "smoke",
                        "description": "basic regressions",
                        "pass_threshold": 90,
                        "scenarios": [
                            {
                                "name": "time",
                                "prompt": "what time is it",
                                "must_contain": ["time"],
                            }
                        ],
                    }
                ]
            }
        )
    )

    settings = Settings(db_path=str(tmp_path / "api_evals_strict.db"), eval_suites_file=str(suites_file))
    app = create_app(settings)
    client = TestClient(app)

    gated = client.post("/benchmark/gate", json={"suite_name": "smoke", "min_score": 101})
    assert gated.status_code == 200
    gbody = gated.json()
    assert gbody["ok"] is False
    assert gbody["threshold"] == 101
