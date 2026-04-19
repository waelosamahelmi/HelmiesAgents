from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.gateways.router import GatewayRouter, GatewayEvent
from helmiesagents.models import RequestContext
from helmiesagents.workforce import WorkforceService


def test_gateway_router(tmp_path):
    settings = Settings(db_path=str(tmp_path / "gw.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)

    router = GatewayRouter(agent, memory)
    out = router.handle_event(
        GatewayEvent(platform="slack", channel_id="C1", user_id="U1", text="what time is it"),
        ctx=RequestContext(tenant_id="default", user_id="U1", roles=["admin"]),
    )

    assert out["platform"] == "slack"
    assert "response" in out


def test_gateway_router_can_route_to_hired_agent_persona(tmp_path):
    settings = Settings(db_path=str(tmp_path / "gw2.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)

    workforce = WorkforceService(memory)
    hired_id = workforce.hire_agent(
        tenant_id="default",
        name="Mia",
        job_title="Senior Marketing Manager",
        description="Own launch campaigns",
        system_prompt="You are Mia, focused on demand generation and campaign outcomes.",
        cv_text="10 years in growth marketing",
        skills=["campaign planning", "analytics"],
        slack_channels=["#marketing"],
    )

    router = GatewayRouter(agent, memory)
    out = router.handle_event(
        GatewayEvent(
            platform="slack",
            channel_id="C1",
            user_id="U1",
            text="Draft quick launch KPI plan",
            agent_id=hired_id,
            thread_id="wf-task-42",
        ),
        ctx=RequestContext(tenant_id="default", user_id="U1", roles=["admin"]),
    )

    assert out["routed_agent_id"] == hired_id
    assert out["routed_agent_name"] == "Mia"

    bus = memory.list_workforce_bus_messages(tenant_id="default", thread_id="wf-task-42")
    assert len(bus) >= 1
    assert bus[0]["metadata"].get("kind") == "gateway_response"
