from __future__ import annotations

import json
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.workflow.engine import WorkflowEngine
from helmiesagents.api.server import create_app


app = typer.Typer(help="HelmiesAgents CLI")
console = Console()


def _build_runtime() -> tuple[Settings, HelmiesAgent, MemoryStore, WorkflowEngine]:
    settings = Settings.from_env()
    settings.ensure_dirs()
    memory = MemoryStore(settings.db_path)
    tools = ToolRegistry()
    install_builtin_tools(tools, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=tools)
    workflow = WorkflowEngine(agent=agent)
    return settings, agent, memory, workflow


@app.command()
def chat(message: str, session: str = typer.Option("cli-default", "--session")):
    """Send a single message to HelmiesAgents."""
    _, agent, _, _ = _build_runtime()
    res = agent.chat(session_id=session, user_message=message)
    console.print(res.text)
    if res.tools_executed:
        console.print("\n[bold]Tools executed:[/bold]")
        console.print_json(json.dumps(res.tools_executed))


@app.command()
def repl(session: str = typer.Option("cli-repl", "--session")):
    """Start interactive REPL chat."""
    _, agent, _, _ = _build_runtime()
    console.print("[bold cyan]HelmiesAgents REPL[/bold cyan] (type 'exit' to quit)")
    while True:
        msg = typer.prompt("you")
        if msg.strip().lower() in {"exit", "quit"}:
            break
        res = agent.chat(session_id=session, user_message=msg)
        console.print(f"[green]agent:[/green] {res.text}\n")


@app.command("run-workflow")
def run_workflow(workflow_path: str, session: str = typer.Option("workflow-cli", "--session")):
    """Run a YAML workflow."""
    _, _, _, wf = _build_runtime()
    result = wf.run(workflow_path=workflow_path, session_id=session)
    console.print_json(json.dumps({"name": result.name, "status": result.status, "outputs": result.outputs}))


@app.command()
def memory_search(query: str, limit: int = 10):
    """Search memory messages."""
    _, _, memory, _ = _build_runtime()
    hits = memory.search_messages(query, limit=limit)
    console.print_json(json.dumps([h.__dict__ for h in hits]))


@app.command()
def serve(host: str = "0.0.0.0", port: int = 8787):
    """Run FastAPI server + web UI."""
    app_instance = create_app(Settings.from_env())
    uvicorn.run(app_instance, host=host, port=port)


@app.command()
def init_project(path: str = typer.Argument("./helmies_project")):
    """Initialize project workspace structure."""
    p = Path(path)
    (p / "workflows").mkdir(parents=True, exist_ok=True)
    (p / "skills").mkdir(parents=True, exist_ok=True)
    sample = p / "workflows" / "hello.yaml"
    if not sample.exists():
        sample.write_text(
            """
name: hello-workflow
nodes:
  - id: intro
    type: prompt
    prompt: "Generate a short launch checklist for HelmiesAgents"
""".strip()
        )
    console.print(f"Initialized workspace at {p}")


if __name__ == "__main__":
    app()
