from __future__ import annotations

import asyncio
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import yaml

from helmiesagents.config import Settings
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.execution.async_runner import AsyncExecutionManager, AsyncJob
from helmiesagents.execution.sqlite_queue import SQLiteQueueManager
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import CancellationToken, RequestContext


@dataclass
class WorkflowResult:
    run_id: str
    name: str
    status: str
    outputs: dict[str, Any]


class WorkflowEngine:
    def __init__(self, agent: HelmiesAgent, memory: MemoryStore, settings: Settings | None = None) -> None:
        self.agent = agent
        self.memory = memory
        self.settings = settings or Settings.from_env()

        # In-memory async backend (legacy)
        self.async_exec = AsyncExecutionManager()

        # Distributed queue backend (sqlite durable queue for now)
        self.queue_backend = (self.settings.queue_backend or "memory").lower()
        self.queue: SQLiteQueueManager | None = None
        if self.queue_backend == "sqlite":
            self.queue = SQLiteQueueManager(self.settings.db_path)

        self._worker_task: asyncio.Task | None = None

    def _execute_sync(self, workflow_path: str, session_id: str, ctx: RequestContext, cancel_token: CancellationToken | None = None) -> WorkflowResult:
        data = yaml.safe_load(Path(workflow_path).read_text())
        name = data.get("name", "unnamed-workflow")
        nodes = data.get("nodes", [])
        run_id = str(uuid4())

        outputs: dict[str, Any] = {}
        executed: set[str] = set()

        while len(executed) < len(nodes):
            progressed = False
            for node in nodes:
                if cancel_token and cancel_token.cancelled:
                    self.memory.save_workflow_run(
                        run_id=run_id,
                        tenant_id=ctx.tenant_id,
                        session_id=session_id,
                        workflow_name=name,
                        status="cancelled",
                        outputs_json=json.dumps(outputs),
                    )
                    return WorkflowResult(run_id=run_id, name=name, status="cancelled", outputs=outputs)

                nid = node["id"]
                if nid in executed:
                    continue
                deps = node.get("depends_on", [])
                if any(d not in executed for d in deps):
                    continue

                kind = node.get("type", "prompt")
                if kind == "prompt":
                    prompt = node.get("prompt", "")
                    res = self.agent.chat(session_id=f"{session_id}:{nid}", user_message=prompt, ctx=ctx)
                    outputs[nid] = {"text": res.text, "tools": res.tools_executed}
                elif kind == "shell":
                    cmd = node.get("command", "")
                    proc = subprocess.run(
                        cmd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=int(node.get("timeout", 120)),
                    )
                    outputs[nid] = {"exit_code": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
                elif kind == "python":
                    code = node.get("code", "")
                    env: dict[str, Any] = {"outputs": outputs}
                    exec(code, {}, env)
                    outputs[nid] = {"result": env.get("result")}
                elif kind == "http":
                    url = node.get("url", "")
                    method = str(node.get("method", "GET")).upper()
                    with httpx.Client(timeout=int(node.get("timeout", 30))) as client:
                        if method == "GET":
                            r = client.get(url)
                        else:
                            r = client.post(url, json=node.get("json", {}))
                    outputs[nid] = {"status": r.status_code, "body": r.text[:5000]}
                else:
                    outputs[nid] = {"error": f"Unsupported node type: {kind}"}

                executed.add(nid)
                progressed = True

            if not progressed:
                result = WorkflowResult(
                    run_id=run_id,
                    name=name,
                    status="failed",
                    outputs={**outputs, "_error": "Dependency resolution failed"},
                )
                self.memory.save_workflow_run(
                    run_id=run_id,
                    tenant_id=ctx.tenant_id,
                    session_id=session_id,
                    workflow_name=name,
                    status=result.status,
                    outputs_json=json.dumps(result.outputs),
                )
                return result

        result = WorkflowResult(run_id=run_id, name=name, status="success", outputs=outputs)
        self.memory.save_workflow_run(
            run_id=run_id,
            tenant_id=ctx.tenant_id,
            session_id=session_id,
            workflow_name=name,
            status=result.status,
            outputs_json=json.dumps(result.outputs),
        )
        return result

    def run(self, workflow_path: str, session_id: str = "workflow", ctx: RequestContext | None = None, cancel_token: CancellationToken | None = None) -> WorkflowResult:
        ctx = ctx or RequestContext()
        return self._execute_sync(workflow_path=workflow_path, session_id=session_id, ctx=ctx, cancel_token=cancel_token)

    def _serialize_ctx(self, ctx: RequestContext) -> dict[str, Any]:
        return {
            "tenant_id": ctx.tenant_id,
            "user_id": ctx.user_id,
            "roles": list(ctx.roles),
            "auto_approve": bool(ctx.auto_approve),
        }

    def _deserialize_ctx(self, payload: dict[str, Any]) -> RequestContext:
        return RequestContext(
            tenant_id=str(payload.get("tenant_id", "default")),
            user_id=str(payload.get("user_id", "anonymous")),
            roles=list(payload.get("roles", ["viewer"])),
            auto_approve=bool(payload.get("auto_approve", False)),
        )

    async def run_async(self, workflow_path: str, session_id: str = "workflow", ctx: RequestContext | None = None) -> str:
        ctx = ctx or RequestContext()

        if self.queue_backend == "sqlite":
            assert self.queue is not None
            payload = {
                "workflow_path": workflow_path,
                "session_id": session_id,
                "ctx": self._serialize_ctx(ctx),
            }
            job_id = self.queue.enqueue("workflow", payload)
            await self._maybe_start_worker()
            return job_id

        async def _coro(token: CancellationToken):
            await asyncio.sleep(0)
            result = self._execute_sync(workflow_path, session_id, ctx, cancel_token=token)
            return {
                "run_id": result.run_id,
                "name": result.name,
                "status": result.status,
                "outputs": result.outputs,
            }

        return await self.async_exec.run_coro("workflow", _coro)

    async def _maybe_start_worker(self) -> None:
        if self.queue_backend != "sqlite":
            return
        if not self.settings.queue_autostart_worker:
            return
        if self._worker_task and not self._worker_task.done():
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._worker_task = loop.create_task(self._worker_loop())

    async def _worker_loop(self) -> None:
        while True:
            try:
                processed = self.process_queue_once(worker_id="autostart")
            except Exception:
                processed = False
            if processed:
                await asyncio.sleep(0)
            else:
                await asyncio.sleep(max(0.1, float(self.settings.queue_poll_interval_seconds)))

    def process_queue_once(self, worker_id: str = "manual") -> bool:
        if self.queue_backend != "sqlite":
            return False
        assert self.queue is not None

        claim = self.queue.claim_next(kind="workflow", worker_id=worker_id)
        if not claim:
            return False

        payload = claim.payload
        workflow_path = str(payload.get("workflow_path", ""))
        session_id = str(payload.get("session_id", "workflow"))
        ctx = self._deserialize_ctx(payload.get("ctx", {}))

        try:
            result = self._execute_sync(workflow_path=workflow_path, session_id=session_id, ctx=ctx)
            self.queue.mark_completed(
                claim.id,
                {
                    "run_id": result.run_id,
                    "name": result.name,
                    "status": result.status,
                    "outputs": result.outputs,
                },
            )
        except Exception as e:
            self.queue.mark_failed(claim.id, str(e))
        return True

    def get_job(self, job_id: str) -> AsyncJob | None:
        if self.queue_backend == "sqlite":
            assert self.queue is not None
            return self.queue.get_job(job_id)
        return self.async_exec.get_job(job_id)

    def cancel_job(self, job_id: str) -> bool:
        if self.queue_backend == "sqlite":
            assert self.queue is not None
            return self.queue.cancel(job_id)
        return self.async_exec.cancel(job_id)

    def list_jobs(self, limit: int = 100, status: str | None = None) -> list[AsyncJob]:
        if self.queue_backend == "sqlite":
            assert self.queue is not None
            return self.queue.list_jobs(limit=limit, status=status, kind="workflow")

        jobs = list(self.async_exec.jobs.values())
        if status:
            jobs = [j for j in jobs if j.status == status]
        return jobs[:limit]
