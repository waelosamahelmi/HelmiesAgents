from __future__ import annotations

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry


class _SubrunAwareProvider:
    name = "subrun-aware-test"

    def __init__(self):
        self.calls: list[str] = []

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        self.calls.append(user_prompt)
        p = user_prompt.lower()

        if "subrun" in p or "investigate subtask" in p:
            return "Subrun result: gathered concrete findings for this slice."

        # force main answer to miss anchors initially; repaired/final answer should include them
        if "user request:" in p and "time" in p and "file" in p:
            return "I looked into it."

        return "Final consolidated answer includes time and files with actionable next steps."

    def stream_generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None):
        yield from "Final consolidated answer includes time and files with actionable next steps."


def _build_agent(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "subruns.db"),
        critic_enabled=True,
        critic_max_retries=1,
        critic_min_score=0.7,
        autonomous_subruns_enabled=True,
        autonomous_subruns_max=2,
        autonomous_subruns_verify=True,
    )
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    return HelmiesAgent(settings=settings, memory=memory, tools=reg)


def test_agent_autonomous_subruns_metadata_and_execution(tmp_path):
    agent = _build_agent(tmp_path)
    provider = _SubrunAwareProvider()
    agent.provider = provider

    res = agent.chat(
        "sr1",
        "Analyze both: what time is it and list files",
        ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]),
    )

    assert res.quality is not None
    assert "autonomy" in res.quality
    auto = res.quality["autonomy"]
    assert auto["enabled"] is True
    assert auto["subruns_executed"] >= 1
    assert len(auto["subruns"]) >= 1
    assert any("findings" in s for s in [x["result_preview"].lower() for x in auto["subruns"]])


def test_agent_autonomous_subruns_disabled(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "subruns_off.db"),
        autonomous_subruns_enabled=False,
        autonomous_subruns_max=2,
        autonomous_subruns_verify=True,
    )
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)
    provider = _SubrunAwareProvider()
    agent.provider = provider

    res = agent.chat(
        "sr2",
        "Analyze both: what time is it and list files",
        ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]),
    )

    assert res.quality is not None
    auto = res.quality["autonomy"]
    assert auto["enabled"] is False
    assert auto["subruns_executed"] == 0


def test_api_chat_includes_autonomy_quality_block(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "api_subruns.db"),
        autonomous_subruns_enabled=True,
        autonomous_subruns_max=2,
        autonomous_subruns_verify=True,
    )
    app = create_app(settings)
    client = TestClient(app)

    payload = {"session_id": "api-sr", "message": "Analyze both: what time is it and list files"}
    r = client.post("/chat", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert "quality" in body
    assert "autonomy" in body["quality"]
