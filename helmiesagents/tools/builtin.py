from __future__ import annotations

from datetime import datetime
import json
import re
from pathlib import Path
import subprocess
import httpx

from helmiesagents.tools.registry import Tool, ToolRegistry
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.ingestion import to_markdown


def install_builtin_tools(registry: ToolRegistry, memory: MemoryStore) -> None:
    def time_now(_: dict) -> dict:
        return {"iso": datetime.utcnow().isoformat()}

    def read_file(args: dict) -> dict:
        path = Path(str(args.get("path", "")))
        if not path.exists():
            raise FileNotFoundError(str(path))
        text = path.read_text(errors="ignore")
        return {"path": str(path), "content": text[:20000]}

    def write_file(args: dict) -> dict:
        path = Path(str(args.get("path", "")))
        content = str(args.get("content", ""))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        return {"path": str(path), "written": len(content)}

    def search_files(args: dict) -> dict:
        pattern = str(args.get("pattern", "*"))
        base = Path(str(args.get("path", ".")))
        limit = int(args.get("limit", 50))
        files = []
        for p in base.rglob(pattern):
            if p.is_file() and ".git" not in p.parts:
                files.append(str(p))
            if len(files) >= limit:
                break
        return {"count": len(files), "files": files}

    def run_shell(args: dict) -> dict:
        command = str(args.get("command", ""))
        timeout = int(args.get("timeout", 90))

        deny = [r"rm\s+-rf\s+/", r":\(\)\{", r"mkfs", r"shutdown", r"reboot"]
        for d in deny:
            if re.search(d, command):
                raise PermissionError("Command blocked by safety policy")

        proc = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout[:20000],
            "stderr": proc.stderr[:20000],
        }

    def http_get(args: dict) -> dict:
        url = str(args.get("url", ""))
        with httpx.Client(timeout=30) as client:
            res = client.get(url)
        return {
            "status": res.status_code,
            "url": str(res.url),
            "body": res.text[:20000],
        }

    def memory_search(args: dict) -> dict:
        query = str(args.get("query", ""))
        hits = memory.search_messages(query, limit=int(args.get("limit", 10)))
        return {"hits": [h.__dict__ for h in hits]}

    def ingest_to_markdown(args: dict) -> dict:
        path = str(args.get("path", ""))
        return to_markdown(path)

    registry.register(Tool("time_now", "Get current UTC time", time_now))
    registry.register(Tool("read_file", "Read a file from disk", read_file))
    registry.register(Tool("write_file", "Write content to a file", write_file))
    registry.register(Tool("search_files", "Search files by glob pattern", search_files))
    registry.register(Tool("run_shell", "Execute shell command with safety policy", run_shell))
    registry.register(Tool("http_get", "Perform HTTP GET request", http_get))
    registry.register(Tool("memory_search", "Search stored session memory", memory_search))
    registry.register(Tool("ingest_to_markdown", "Convert a file to markdown text", ingest_to_markdown))
