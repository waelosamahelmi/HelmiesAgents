from __future__ import annotations

from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry


class _FlakyProvider:
    name = "flaky-test"

    def __init__(self):
        self.calls = 0

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        self.calls += 1
        if self.calls == 1:
            return "This response misses the key term."
        return "The current time was retrieved and verified."

    def stream_generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None):
        yield from "The current time was retrieved and verified."


class _AlwaysBadProvider:
    name = "always-bad-test"

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        return "Irrelevant output without required lexical anchors."

    def stream_generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None):
        yield from "Irrelevant output without required lexical anchors."


def _build_agent(tmp_path, *, critic_enabled: bool = True, retries: int = 1, min_score: float = 0.7):
    settings = Settings(
        db_path=str(tmp_path / "critic.db"),
        critic_enabled=critic_enabled,
        critic_max_retries=retries,
        critic_min_score=min_score,
    )
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    return HelmiesAgent(settings=settings, memory=memory, tools=reg)


def test_critic_repairs_response_when_retry_allowed(tmp_path):
    agent = _build_agent(tmp_path, critic_enabled=True, retries=1, min_score=0.7)
    flaky = _FlakyProvider()
    agent.provider = flaky

    res = agent.chat("c1", "what time is it", ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]))

    assert flaky.calls == 2
    assert res.quality is not None
    assert res.quality["enabled"] is True
    assert len(res.quality["attempts"]) == 2
    assert res.quality["final_pass"] is True


def test_critic_no_retry_when_disabled(tmp_path):
    agent = _build_agent(tmp_path, critic_enabled=False, retries=2, min_score=0.7)
    flaky = _FlakyProvider()
    agent.provider = flaky

    res = agent.chat("c2", "what time is it", ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]))

    assert flaky.calls == 1
    assert res.quality is not None
    assert res.quality["enabled"] is False
    assert len(res.quality["attempts"]) == 1


def test_critic_marks_failure_when_still_bad_after_retries(tmp_path):
    agent = _build_agent(tmp_path, critic_enabled=True, retries=2, min_score=0.9)
    bad = _AlwaysBadProvider()
    agent.provider = bad

    res = agent.chat("c3", "what time is it", ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]))

    assert res.quality is not None
    assert len(res.quality["attempts"]) == 3
    assert res.quality["final_pass"] is False
