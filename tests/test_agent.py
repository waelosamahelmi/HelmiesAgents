from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.models import RequestContext


def build_agent(tmp_path):
    settings = Settings(db_path=str(tmp_path / "agent.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    return HelmiesAgent(settings=settings, memory=memory, tools=reg)


def test_agent_basic_response(tmp_path):
    agent = build_agent(tmp_path)
    res = agent.chat("t1", "hello", ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]))
    assert isinstance(res.text, str) and len(res.text) > 0
    assert len(res.plan) >= 1


def test_agent_tool_execution_time(tmp_path):
    agent = build_agent(tmp_path)
    res = agent.chat("t1", "what time is it", ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]))
    assert any(t["tool"] == "time_now" for t in res.tools_executed)
