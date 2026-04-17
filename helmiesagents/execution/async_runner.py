from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from helmiesagents.models import CancellationToken


@dataclass
class AsyncJob:
    id: str
    kind: str
    status: str
    result: dict[str, Any] | None
    error: str | None


class AsyncExecutionManager:
    def __init__(self) -> None:
        self.jobs: dict[str, AsyncJob] = {}
        self.tokens: dict[str, CancellationToken] = {}

    async def run_coro(self, kind: str, coro_factory):
        job_id = str(uuid4())
        token = CancellationToken()
        self.tokens[job_id] = token
        self.jobs[job_id] = AsyncJob(id=job_id, kind=kind, status="running", result=None, error=None)

        async def _runner():
            try:
                result = await coro_factory(token)
                if token.cancelled:
                    self.jobs[job_id].status = "cancelled"
                    self.jobs[job_id].result = {"cancelled": True}
                else:
                    self.jobs[job_id].status = "completed"
                    self.jobs[job_id].result = result
            except Exception as e:
                self.jobs[job_id].status = "failed"
                self.jobs[job_id].error = str(e)

        asyncio.create_task(_runner())
        return job_id

    def get_job(self, job_id: str) -> AsyncJob | None:
        return self.jobs.get(job_id)

    def cancel(self, job_id: str) -> bool:
        token = self.tokens.get(job_id)
        if not token:
            return False
        token.cancel()
        return True
