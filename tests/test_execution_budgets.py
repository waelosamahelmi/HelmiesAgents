from __future__ import annotations

import yaml

from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry


class _AlwaysBadProvider:
    name = "always-bad-budget-test"

    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        self.calls += 1
        return "This answer intentionally misses required anchors."

    def stream_generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None):
        yield from "This answer intentionally misses required anchors."


class _SubrunProvider:
    name = "subrun-budget-test"

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        low = user_prompt.lower()
        if "subtask:" in low or "investigate subtask" in low:
            return "Subrun findings for this slice."
        return "Final answer includes time and files for completion."

    def stream_generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None):
        yield from "Final answer includes time and files for completion."


class _TwoToolsProvider:
    name = "two-tools-budget-test"

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        return (
            '[[tool:time_now {}]]\n'
            '[[tool:search_files {"pattern":"*","path":"."}]]\n'
            'Done.'
        )

    def stream_generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None):
        yield from self.generate(system_prompt, user_prompt, model_override)


def _make_agent(tmp_path, *, budget_file: str) -> HelmiesAgent:
    settings = Settings(
        db_path=str(tmp_path / "budget.db"),
        critic_enabled=True,
        critic_max_retries=3,
        critic_min_score=0.7,
        autonomous_subruns_enabled=True,
        autonomous_subruns_max=4,
        autonomous_subruns_verify=True,
        execution_budget_file=budget_file,
    )
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    return HelmiesAgent(settings=settings, memory=memory, tools=reg)


def test_role_budget_caps_critic_retries(tmp_path):
    policy_file = tmp_path / "budgets.yaml"
    policy_file.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "roles": {
                    "viewer": {"max_critic_retries": 0},
                },
            }
        )
    )

    agent = _make_agent(tmp_path, budget_file=str(policy_file))
    provider = _AlwaysBadProvider()
    agent.provider = provider

    res = agent.chat(
        "b1",
        "what time is it",
        ctx=RequestContext(tenant_id="default", user_id="u1", roles=["viewer"]),
    )

    assert provider.calls == 1
    assert res.quality is not None
    assert res.quality["budget"]["max_critic_retries"] == 0
    assert len(res.quality["attempts"]) == 1


def test_role_budget_caps_subruns(tmp_path):
    policy_file = tmp_path / "budgets.yaml"
    policy_file.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "roles": {
                    "viewer": {"max_subruns": 1},
                },
            }
        )
    )

    agent = _make_agent(tmp_path, budget_file=str(policy_file))
    agent.provider = _SubrunProvider()

    res = agent.chat(
        "b2",
        "Analyze both: what time is it and list files",
        ctx=RequestContext(tenant_id="default", user_id="u1", roles=["viewer"]),
    )

    assert res.quality is not None
    auto = res.quality["autonomy"]
    assert auto["subruns_executed"] == 1


def test_role_budget_caps_tool_calls(tmp_path):
    policy_file = tmp_path / "budgets.yaml"
    policy_file.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "roles": {
                    "viewer": {"max_tool_calls": 1},
                },
            }
        )
    )

    agent = _make_agent(tmp_path, budget_file=str(policy_file))
    agent.provider = _TwoToolsProvider()

    res = agent.chat(
        "b3",
        "please run tools",
        ctx=RequestContext(tenant_id="default", user_id="u1", roles=["viewer"]),
    )

    assert res.quality is not None
    assert res.quality["budget"]["max_tool_calls"] == 1

    assert len(res.tools_executed) >= 2
    assert res.tools_executed[0]["tool"] == "time_now"
    assert "result" in res.tools_executed[0]

    assert res.tools_executed[1]["tool"] == "search_files"
    assert res.tools_executed[1].get("budget_blocked") is True
