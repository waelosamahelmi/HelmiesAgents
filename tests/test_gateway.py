from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.gateways.router import GatewayRouter, GatewayEvent
from helmiesagents.models import RequestContext


def test_gateway_router(tmp_path):
    settings = Settings(db_path=str(tmp_path / "gw.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)

    router = GatewayRouter(agent)
    out = router.handle_event(
        GatewayEvent(platform="slack", channel_id="C1", user_id="U1", text="what time is it"),
        ctx=RequestContext(tenant_id="default", user_id="U1", roles=["admin"]),
    )

    assert out["platform"] == "slack"
    assert "response" in out
