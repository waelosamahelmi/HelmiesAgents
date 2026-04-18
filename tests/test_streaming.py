from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry


def build_agent(tmp_path):
    settings = Settings(db_path=str(tmp_path / "stream.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    return HelmiesAgent(settings=settings, memory=memory, tools=reg), memory


def test_agent_stream_chat_emits_events(tmp_path):
    agent, memory = build_agent(tmp_path)

    events = list(
        agent.stream_chat(
            session_id="s-stream-1",
            user_message="what time is it",
            ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]),
        )
    )

    assert events[0].type == "meta"
    assert any(e.type == "token" for e in events)
    assert any(e.type == "model_output" for e in events)
    final = [e for e in events if e.type == "final"][0]
    assert "response" in final.data
    assert any(t["tool"] == "time_now" for t in final.data["tools_executed"])
    assert "quality" in final.data

    saved = memory.get_recent_messages("default", "u1", "s-stream-1", limit=5)
    assert any(m.role == "assistant" for m in saved)


def test_websocket_chat_stream_endpoint(tmp_path):
    settings = Settings(db_path=str(tmp_path / "api_stream.db"))
    app = create_app(settings)
    client = TestClient(app)

    events = []
    with client.websocket_connect("/chat/ws") as ws:
        ws.send_json({"session_id": "ws1", "message": "what time is it"})
        while True:
            try:
                events.append(ws.receive_json())
            except WebSocketDisconnect:
                break

    assert any(e.get("type") == "meta" for e in events)
    assert any(e.get("type") == "token" for e in events)
    assert any(e.get("type") == "model_output" for e in events)
    final = [e for e in events if e.get("type") == "final"][0]
    assert "response" in final
    assert any(t["tool"] == "time_now" for t in final["tools_executed"])
    assert "quality" in final
    assert events[-1]["type"] == "done"


def test_websocket_chat_stream_rejects_empty_message(tmp_path):
    settings = Settings(db_path=str(tmp_path / "api_stream_empty.db"))
    app = create_app(settings)
    client = TestClient(app)

    with client.websocket_connect("/chat/ws") as ws:
        ws.send_json({"session_id": "ws2", "message": ""})
        first = ws.receive_json()
        assert first["type"] == "error"
        assert "non-empty" in first["message"]
