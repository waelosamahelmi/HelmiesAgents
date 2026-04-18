from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from helmiesagents.execution.async_runner import AsyncJob


@dataclass
class QueueClaim:
    id: str
    kind: str
    payload: dict[str, Any]


class SQLiteQueueManager:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_jobs (
                    id TEXT PRIMARY KEY,
                    kind TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT,
                    worker_id TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_workflow_jobs_status_created ON workflow_jobs(status, created_at)")

    def enqueue(self, kind: str, payload: dict[str, Any]) -> str:
        job_id = str(uuid4())
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO workflow_jobs(id, kind, status, payload_json, created_at, updated_at) VALUES(?,?,?,?,?,?)",
                (job_id, kind, "queued", json.dumps(payload), now, now),
            )
        return job_id

    def get_job(self, job_id: str) -> AsyncJob | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM workflow_jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            return None
        return AsyncJob(
            id=row["id"],
            kind=row["kind"],
            status=row["status"],
            result=json.loads(row["result_json"]) if row["result_json"] else None,
            error=row["error"],
        )

    def list_jobs(self, limit: int = 100, status: str | None = None, kind: str | None = None) -> list[AsyncJob]:
        query = "SELECT * FROM workflow_jobs"
        parts: list[str] = []
        args: list[Any] = []

        if status:
            parts.append("status=?")
            args.append(status)
        if kind:
            parts.append("kind=?")
            args.append(kind)

        if parts:
            query += " WHERE " + " AND ".join(parts)
        query += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)

        with self._connect() as conn:
            rows = conn.execute(query, tuple(args)).fetchall()

        out: list[AsyncJob] = []
        for row in rows:
            out.append(
                AsyncJob(
                    id=row["id"],
                    kind=row["kind"],
                    status=row["status"],
                    result=json.loads(row["result_json"]) if row["result_json"] else None,
                    error=row["error"],
                )
            )
        return out

    def cancel(self, job_id: str) -> bool:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE workflow_jobs SET status='cancelled', updated_at=? WHERE id=? AND status IN ('queued','running')",
                (now, job_id),
            )
        return cur.rowcount > 0

    def claim_next(self, kind: str = "workflow", worker_id: str = "worker") -> QueueClaim | None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, kind, payload_json FROM workflow_jobs WHERE status='queued' AND kind=? ORDER BY created_at ASC LIMIT 1",
                (kind,),
            ).fetchone()
            if not row:
                return None

            cur = conn.execute(
                "UPDATE workflow_jobs SET status='running', worker_id=?, updated_at=? WHERE id=? AND status='queued'",
                (worker_id, now, row["id"]),
            )
            if cur.rowcount == 0:
                return None

            return QueueClaim(
                id=row["id"],
                kind=row["kind"],
                payload=json.loads(row["payload_json"]),
            )

    def mark_completed(self, job_id: str, result: dict[str, Any]) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE workflow_jobs SET status='completed', result_json=?, updated_at=? WHERE id=?",
                (json.dumps(result), now, job_id),
            )

    def mark_failed(self, job_id: str, error: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE workflow_jobs SET status='failed', error=?, updated_at=? WHERE id=?",
                (error, now, job_id),
            )
