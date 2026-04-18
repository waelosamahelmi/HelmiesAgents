import asyncio

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import RequestContext
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.workflow.engine import WorkflowEngine


def _make_workflow(path, prompt: str = "what time is it"):
    path.write_text(
        f"""
name: queue-test
nodes:
  - id: p1
    type: prompt
    prompt: {prompt!r}
""".strip()
    )


def test_distributed_queue_lifecycle_engine(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "queue_engine.db"),
        queue_backend="sqlite",
        queue_autostart_worker=False,
    )
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)
    engine = WorkflowEngine(agent=agent, memory=memory, settings=settings)

    wf = tmp_path / "wf_queue.yaml"
    _make_workflow(wf)

    job_id = asyncio.run(
        engine.run_async(
            workflow_path=str(wf),
            session_id="q-session",
            ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]),
        )
    )

    queued = engine.get_job(job_id)
    assert queued is not None
    assert queued.status == "queued"

    processed = engine.process_queue_once(worker_id="test-worker")
    assert processed is True

    finished = engine.get_job(job_id)
    assert finished is not None
    assert finished.status == "completed"
    assert isinstance(finished.result, dict)
    assert finished.result["status"] == "success"
    assert finished.result["run_id"]


def test_distributed_queue_cancel_before_processing(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "queue_cancel.db"),
        queue_backend="sqlite",
        queue_autostart_worker=False,
    )
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)
    engine = WorkflowEngine(agent=agent, memory=memory, settings=settings)

    wf = tmp_path / "wf_cancel.yaml"
    _make_workflow(wf, prompt="hello")

    job_id = asyncio.run(
        engine.run_async(
            workflow_path=str(wf),
            session_id="q-cancel",
            ctx=RequestContext(tenant_id="default", user_id="u1", roles=["admin"]),
        )
    )

    assert engine.cancel_job(job_id) is True

    cancelled = engine.get_job(job_id)
    assert cancelled is not None
    assert cancelled.status == "cancelled"


def test_queue_api_controls_and_status(tmp_path):
    settings = Settings(
        db_path=str(tmp_path / "queue_api.db"),
        queue_backend="sqlite",
        queue_autostart_worker=False,
    )
    app = create_app(settings)
    client = TestClient(app)

    wf = tmp_path / "wf_api.yaml"
    _make_workflow(wf)

    r = client.post("/workflow/run_async", json={"workflow_path": str(wf), "session_id": "api-q"})
    assert r.status_code == 200
    job_id = r.json()["job_id"]

    queued = client.get(f"/workflow/job/{job_id}")
    assert queued.status_code == 200
    assert queued.json()["status"] == "queued"

    jobs = client.get("/workflow/jobs")
    assert jobs.status_code == 200
    assert any(j["id"] == job_id for j in jobs.json()["jobs"])

    run_once = client.post("/workflow/worker/run_once")
    assert run_once.status_code == 200
    assert run_once.json()["processed"] is True

    done = client.get(f"/workflow/job/{job_id}")
    assert done.status_code == 200
    assert done.json()["status"] == "completed"
