from __future__ import annotations

import asyncio
import json
from pathlib import Path

import typer
import uvicorn
from rich.console import Console

from helmiesagents.api.server import create_app
from helmiesagents.approvals.manager import ApprovalManager
from helmiesagents.benchmark.harness import BenchmarkHarness, BenchmarkScenario
from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.enterprise.compliance import export_audit_logs
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.security.policy import PolicyEngine
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.workflow.engine import WorkflowEngine


app = typer.Typer(help="HelmiesAgents CLI")
console = Console()


def _build_runtime() -> tuple[Settings, HelmiesAgent, MemoryStore, WorkflowEngine, ApprovalManager, BenchmarkHarness]:
    settings = Settings.from_env()
    settings.ensure_dirs()
    memory = MemoryStore(settings.db_path)
    tools = ToolRegistry()
    install_builtin_tools(tools, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=tools)
    workflow = WorkflowEngine(agent=agent, memory=memory, settings=settings)
    approvals = ApprovalManager(memory=memory, policy=PolicyEngine(policy_file=settings.policy_dsl_file))
    benchmark = BenchmarkHarness(agent=agent, memory=memory)
    return settings, agent, memory, workflow, approvals, benchmark


def _ctx(tenant: str, user: str, roles: str, auto_approve: bool) -> RequestContext:
    role_list = [r.strip() for r in roles.split(",") if r.strip()]
    return RequestContext(tenant_id=tenant, user_id=user, roles=role_list or ["viewer"], auto_approve=auto_approve)


@app.command()
def chat(
    message: str,
    session: str = typer.Option("cli-default", "--session"),
    tenant: str = typer.Option("default", "--tenant"),
    user: str = typer.Option("cli-user", "--user"),
    roles: str = typer.Option("admin", "--roles"),
    auto_approve: bool = typer.Option(False, "--auto-approve"),
):
    _, agent, _, _, _, _ = _build_runtime()
    res = agent.chat(session_id=session, user_message=message, ctx=_ctx(tenant, user, roles, auto_approve))
    console.print(res.text)
    if res.tools_executed:
        console.print("\n[bold]Tools executed:[/bold]")
        console.print_json(data=res.tools_executed)


@app.command()
def repl(
    session: str = typer.Option("cli-repl", "--session"),
    tenant: str = typer.Option("default", "--tenant"),
    user: str = typer.Option("cli-user", "--user"),
    roles: str = typer.Option("admin", "--roles"),
    auto_approve: bool = typer.Option(False, "--auto-approve"),
):
    _, agent, _, _, _, _ = _build_runtime()
    ctx = _ctx(tenant, user, roles, auto_approve)
    console.print("[bold cyan]HelmiesAgents REPL[/bold cyan] (type 'exit' to quit)")
    while True:
        msg = typer.prompt("you")
        if msg.strip().lower() in {"exit", "quit"}:
            break
        res = agent.chat(session_id=session, user_message=msg, ctx=ctx)
        console.print(f"[green]agent:[/green] {res.text}\n")


@app.command("run-workflow")
def run_workflow(
    workflow_path: str,
    session: str = typer.Option("workflow-cli", "--session"),
    tenant: str = typer.Option("default", "--tenant"),
    user: str = typer.Option("cli-user", "--user"),
    roles: str = typer.Option("admin", "--roles"),
):
    _, _, _, wf, _, _ = _build_runtime()
    result = wf.run(workflow_path=workflow_path, session_id=session, ctx=_ctx(tenant, user, roles, False))
    console.print_json(json.dumps({"run_id": result.run_id, "name": result.name, "status": result.status, "outputs": result.outputs}))


@app.command("run-workflow-async")
def run_workflow_async(
    workflow_path: str,
    session: str = typer.Option("workflow-cli", "--session"),
    tenant: str = typer.Option("default", "--tenant"),
    user: str = typer.Option("cli-user", "--user"),
    roles: str = typer.Option("admin", "--roles"),
):
    _, _, _, wf, _, _ = _build_runtime()

    async def _go():
        job_id = await wf.run_async(workflow_path=workflow_path, session_id=session, ctx=_ctx(tenant, user, roles, False))
        return job_id

    job_id = asyncio.run(_go())
    console.print({"job_id": job_id})


@app.command("job-status")
def job_status(job_id: str):
    _, _, _, wf, _, _ = _build_runtime()
    job = wf.get_job(job_id)
    if not job:
        console.print("job not found")
        raise typer.Exit(code=1)
    console.print_json(json.dumps(job.__dict__))


@app.command("job-cancel")
def job_cancel(job_id: str):
    _, _, _, wf, _, _ = _build_runtime()
    ok = wf.cancel_job(job_id)
    console.print({"ok": ok})


@app.command("jobs")
def jobs(
    limit: int = typer.Option(50, "--limit"),
    status: str = typer.Option("", "--status"),
):
    _, _, _, wf, _, _ = _build_runtime()
    rows = wf.list_jobs(limit=limit, status=status or None)
    console.print_json(json.dumps({"backend": wf.queue_backend, "jobs": [j.__dict__ for j in rows]}))


@app.command("queue-run-once")
def queue_run_once(worker_id: str = typer.Option("cli-manual", "--worker-id")):
    _, _, _, wf, _, _ = _build_runtime()
    processed = wf.process_queue_once(worker_id=worker_id)
    console.print({"backend": wf.queue_backend, "processed": processed})


@app.command("memory-search")
def memory_search(
    query: str,
    limit: int = 10,
    tenant: str = typer.Option("default", "--tenant"),
):
    _, _, memory, _, _, _ = _build_runtime()
    hits = memory.search_messages(tenant, query, limit=limit)
    console.print_json(json.dumps([h.__dict__ for h in hits]))


@app.command("benchmark-run")
def benchmark_run(
    suite_name: str = typer.Option("default", "--suite"),
    tenant: str = typer.Option("default", "--tenant"),
    user: str = typer.Option("cli-user", "--user"),
    roles: str = typer.Option("admin", "--roles"),
    scenarios_file: str = typer.Option("", "--scenarios-file", help="YAML suites file; if set runs named suite"),
):
    settings, _, _, _, _, bench = _build_runtime()
    ctx = _ctx(tenant, user, roles, False)

    if scenarios_file:
        summary = bench.run_named_suite(ctx, suite_name=suite_name, suites_file=scenarios_file)
    elif settings.eval_suites_file:
        summary = bench.run_named_suite(ctx, suite_name=suite_name, suites_file=settings.eval_suites_file)
    else:
        scenarios = [
            BenchmarkScenario(name="time-tool", prompt="what time is it", must_contain=["time"]),
            BenchmarkScenario(name="file-list", prompt="list files", must_contain=["files"]),
        ]
        summary = bench.run_suite(ctx, suite_name, scenarios)

    console.print_json(json.dumps(summary.__dict__))


@app.command("benchmark-gate")
def benchmark_gate(
    suite_name: str = typer.Option("default", "--suite"),
    tenant: str = typer.Option("default", "--tenant"),
    user: str = typer.Option("cli-user", "--user"),
    roles: str = typer.Option("admin", "--roles"),
    min_score: float = typer.Option(-1.0, "--min-score"),
    scenarios_file: str = typer.Option("", "--scenarios-file"),
):
    settings, _, _, _, _, bench = _build_runtime()
    ctx = _ctx(tenant, user, roles, False)

    suites_file = scenarios_file or settings.eval_suites_file
    if not suites_file:
        console.print("No eval suites file configured. Set --scenarios-file or HELMIES_EVAL_SUITES_FILE")
        raise typer.Exit(code=2)

    threshold = min_score if min_score >= 0 else settings.eval_min_score
    summary = bench.run_named_suite(ctx, suite_name=suite_name, suites_file=suites_file, min_score_override=threshold)
    payload = {"ok": bool(summary.gate_passed), "threshold": threshold, "summary": summary.__dict__}
    console.print_json(json.dumps(payload))
    if not payload["ok"]:
        raise typer.Exit(code=1)


@app.command("benchmark-list")
def benchmark_list(
    tenant: str = typer.Option("default", "--tenant"),
    suite_name: str = typer.Option("", "--suite"),
):
    _, _, memory, _, _, _ = _build_runtime()
    rows = memory.list_benchmark_results(tenant_id=tenant, suite_name=suite_name or None)
    console.print_json(json.dumps(rows))


@app.command("audit-export")
def audit_export(
    out_path: str,
    tenant: str = typer.Option("default", "--tenant"),
):
    _, _, memory, _, _, _ = _build_runtime()
    result = export_audit_logs(memory, tenant_id=tenant, out_path=out_path)
    console.print(result)


@app.command("serve")
def serve(host: str = "0.0.0.0", port: int = 8787):
    app_instance = create_app(Settings.from_env())
    uvicorn.run(app_instance, host=host, port=port)


@app.command("init-project")
def init_project(path: str = typer.Argument("./helmies_project")):
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
