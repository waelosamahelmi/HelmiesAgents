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

from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.execution.async_runner import AsyncExecutionManager
from helmiesagents.memory.store import MemoryStore
from helmiesagents.models import CancellationToken, RequestContext


@dataclass
class WorkflowResult:
    run_id: str
    name: str
    status: str
    outputs: dict[str, Any]


class WorkflowEngine:
    def __init__(self, agent: HelmiesAgent, memory: MemoryStore) -> None:
        self.agent = agent
        self.memory = memory
        self.async_exec = AsyncExecutionManager()

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
                result = WorkflowResult(run_id=run_id, name=name, status="failed", outputs={**outputs, "_error": "Dependency resolution failed"})
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

    async def run_async(self, workflow_path: str, session_id: str = "workflow", ctx: RequestContext | None = None) -> str:
        ctx = ctx or RequestContext()

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
