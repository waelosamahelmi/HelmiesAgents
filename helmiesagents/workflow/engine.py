from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any
import yaml
import httpx

from helmiesagents.core.agent import HelmiesAgent


@dataclass
class WorkflowResult:
    name: str
    status: str
    outputs: dict[str, Any]


class WorkflowEngine:
    def __init__(self, agent: HelmiesAgent) -> None:
        self.agent = agent

    def run(self, workflow_path: str, session_id: str = "workflow") -> WorkflowResult:
        data = yaml.safe_load(Path(workflow_path).read_text())
        name = data.get("name", "unnamed-workflow")
        nodes = data.get("nodes", [])

        outputs: dict[str, Any] = {}
        executed: set[str] = set()

        node_map = {n["id"]: n for n in nodes}

        while len(executed) < len(nodes):
            progressed = False
            for node in nodes:
                nid = node["id"]
                if nid in executed:
                    continue
                deps = node.get("depends_on", [])
                if any(d not in executed for d in deps):
                    continue

                kind = node.get("type", "prompt")
                if kind == "prompt":
                    prompt = node.get("prompt", "")
                    res = self.agent.chat(session_id=f"{session_id}:{nid}", user_message=prompt)
                    outputs[nid] = {"text": res.text, "tools": res.tools_executed}
                elif kind == "shell":
                    cmd = node.get("command", "")
                    proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=int(node.get("timeout", 120)))
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
                return WorkflowResult(name=name, status="failed", outputs={**outputs, "_error": "Dependency resolution failed"})

        return WorkflowResult(name=name, status="success", outputs=outputs)
