from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.workflow.engine import WorkflowEngine


class ChatRequest(BaseModel):
    session_id: str = "default"
    message: str


class SkillRequest(BaseModel):
    name: str
    description: str
    content: str


class WorkflowRequest(BaseModel):
    workflow_path: str
    session_id: str = "workflow"


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.ensure_dirs()

    memory = MemoryStore(settings.db_path)
    registry = ToolRegistry()
    install_builtin_tools(registry, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=registry)
    workflow_engine = WorkflowEngine(agent=agent)

    app = FastAPI(title="HelmiesAgents API", version="0.1.0")

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {
            "ok": True,
            "provider": agent.provider.name,
            "tools": registry.list_tools(),
        }

    @app.post("/chat")
    def chat(req: ChatRequest) -> dict[str, Any]:
        res = agent.chat(session_id=req.session_id, user_message=req.message)
        return {
            "response": res.text,
            "plan": res.plan,
            "tools_executed": res.tools_executed,
        }

    @app.get("/memory/search")
    def memory_search(q: str, limit: int = 10) -> dict[str, Any]:
        hits = memory.search_messages(q, limit=limit)
        return {"hits": [h.__dict__ for h in hits]}

    @app.get("/skills")
    def list_skills() -> dict[str, Any]:
        return {"skills": memory.list_skills()}

    @app.post("/skills")
    def save_skill(req: SkillRequest) -> dict[str, Any]:
        memory.save_skill(req.name, req.description, req.content)
        return {"ok": True}

    @app.post("/workflow/run")
    def run_workflow(req: WorkflowRequest) -> dict[str, Any]:
        result = workflow_engine.run(workflow_path=req.workflow_path, session_id=req.session_id)
        return {"name": result.name, "status": result.status, "outputs": result.outputs}

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return Path(Path(__file__).resolve().parent.parent / "web" / "index.html").read_text()

    return app
