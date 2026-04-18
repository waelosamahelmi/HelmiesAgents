from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class MemoryHit:
    session_id: str
    role: str
    content: str
    created_at: str


class MemoryStore:
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
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    user_id TEXT NOT NULL DEFAULT 'anonymous',
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_tenant_user_session ON messages(tenant_id, user_id, session_id, id)")

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, category, key)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL DEFAULT 'default',
                    name TEXT NOT NULL,
                    description TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, name)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    username TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    roles TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    UNIQUE(tenant_id, username)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    action_hash TEXT NOT NULL,
                    tool_name TEXT NOT NULL,
                    args_json TEXT NOT NULL,
                    reason TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    decided_at TEXT
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    tenant_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    outputs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    suite_name TEXT NOT NULL,
                    scenario_name TEXT NOT NULL,
                    passed INTEGER NOT NULL,
                    score REAL NOT NULL,
                    details_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vault_secrets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value_enc TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(tenant_id, key)
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workforce_agents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    job_title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    system_prompt TEXT NOT NULL,
                    cv_text TEXT NOT NULL,
                    skills_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    slack_channels_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS workforce_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tenant_id TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    assignee_agent_id INTEGER,
                    collaborator_agent_ids_json TEXT NOT NULL,
                    priority TEXT NOT NULL,
                    status TEXT NOT NULL,
                    result_json TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )

    def add_message(self, tenant_id: str, user_id: str, session_id: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(tenant_id, user_id, session_id, role, content, created_at) VALUES(?,?,?,?,?,?)",
                (tenant_id, user_id, session_id, role, content, datetime.utcnow().isoformat()),
            )

    def get_recent_messages(self, tenant_id: str, user_id: str, session_id: str, limit: int = 20) -> list[MemoryHit]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, role, content, created_at FROM messages WHERE tenant_id=? AND user_id=? AND session_id=? ORDER BY id DESC LIMIT ?",
                (tenant_id, user_id, session_id, limit),
            ).fetchall()
        return [MemoryHit(**dict(r)) for r in reversed(rows)]

    def search_messages(self, tenant_id: str, query: str, limit: int = 10) -> list[MemoryHit]:
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, role, content, created_at FROM messages WHERE tenant_id=? AND content LIKE ? ORDER BY id DESC LIMIT ?",
                (tenant_id, like, limit),
            ).fetchall()
        return [MemoryHit(**dict(r)) for r in rows]

    def upsert_fact(self, tenant_id: str, category: str, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO facts(tenant_id, category, key, value, updated_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(tenant_id, category, key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=excluded.updated_at
                """,
                (tenant_id, category, key, value, datetime.utcnow().isoformat()),
            )

    def list_facts(self, tenant_id: str, category: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT category, key, value, updated_at FROM facts WHERE tenant_id=? AND category=? ORDER BY updated_at DESC",
                    (tenant_id, category),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, key, value, updated_at FROM facts WHERE tenant_id=? ORDER BY updated_at DESC",
                    (tenant_id,),
                ).fetchall()
        return [dict(r) for r in rows]

    def save_skill(self, tenant_id: str, name: str, description: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO skills(tenant_id, name, description, content, created_at)
                VALUES(?,?,?,?,?)
                ON CONFLICT(tenant_id, name) DO UPDATE SET
                    description=excluded.description,
                    content=excluded.content
                """,
                (tenant_id, name, description, content, datetime.utcnow().isoformat()),
            )

    def list_skills(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, description, created_at FROM skills WHERE tenant_id=? ORDER BY name ASC",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_skill(self, tenant_id: str, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name, description, content, created_at FROM skills WHERE tenant_id=? AND name=?",
                (tenant_id, name),
            ).fetchone()
        return dict(row) if row else None

    def log_audit(self, tenant_id: str, user_id: str, event_type: str, payload_json: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO audit_logs(tenant_id, user_id, event_type, payload_json, created_at) VALUES(?,?,?,?,?)",
                (tenant_id, user_id, event_type, payload_json, datetime.utcnow().isoformat()),
            )

    def list_audit(self, tenant_id: str, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT tenant_id, user_id, event_type, payload_json, created_at FROM audit_logs WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_approval(self, tenant_id: str, user_id: str, action_hash: str, tool_name: str, args_json: str, reason: str | None, status: str = "pending") -> int:
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO approvals(tenant_id, user_id, action_hash, tool_name, args_json, reason, status, created_at) VALUES(?,?,?,?,?,?,?,?)",
                (tenant_id, user_id, action_hash, tool_name, args_json, reason, status, datetime.utcnow().isoformat()),
            )
            return int(cur.lastrowid)

    def get_approval(self, approval_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM approvals WHERE id=?",
                (approval_id,),
            ).fetchone()
        return dict(row) if row else None

    def set_approval_status(self, approval_id: int, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE approvals SET status=?, decided_at=? WHERE id=?",
                (status, datetime.utcnow().isoformat(), approval_id),
            )

    def save_workflow_run(self, run_id: str, tenant_id: str, session_id: str, workflow_name: str, status: str, outputs_json: str) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO workflow_runs(id, tenant_id, session_id, workflow_name, status, outputs_json, created_at, updated_at)
                VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    outputs_json=excluded.outputs_json,
                    updated_at=excluded.updated_at
                """,
                (run_id, tenant_id, session_id, workflow_name, status, outputs_json, now, now),
            )

    def get_workflow_run(self, run_id: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM workflow_runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def list_workflow_runs(self, tenant_id: str, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workflow_runs WHERE tenant_id=? ORDER BY updated_at DESC LIMIT ?",
                (tenant_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def add_benchmark_result(self, tenant_id: str, suite_name: str, scenario_name: str, passed: bool, score: float, details_json: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO benchmark_results(tenant_id, suite_name, scenario_name, passed, score, details_json, created_at) VALUES(?,?,?,?,?,?,?)",
                (tenant_id, suite_name, scenario_name, int(passed), score, details_json, datetime.utcnow().isoformat()),
            )

    def list_benchmark_results(self, tenant_id: str, suite_name: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if suite_name:
                rows = conn.execute(
                    "SELECT * FROM benchmark_results WHERE tenant_id=? AND suite_name=? ORDER BY id DESC LIMIT ?",
                    (tenant_id, suite_name, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM benchmark_results WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                    (tenant_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    # Workforce / agent team management
    def create_workforce_agent(
        self,
        *,
        tenant_id: str,
        name: str,
        job_title: str,
        description: str,
        system_prompt: str,
        cv_text: str,
        skills: list[str],
        status: str = "hired",
        slack_channels: list[str] | None = None,
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workforce_agents(
                    tenant_id, name, job_title, description, system_prompt, cv_text,
                    skills_json, status, slack_channels_json, created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    name,
                    job_title,
                    description,
                    system_prompt,
                    cv_text,
                    json.dumps(skills or []),
                    status,
                    json.dumps(slack_channels or []),
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def list_workforce_agents(self, tenant_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM workforce_agents WHERE tenant_id=? ORDER BY id DESC",
                (tenant_id,),
            ).fetchall()

        out: list[dict[str, Any]] = []
        for r in rows:
            row = dict(r)
            row["skills"] = json.loads(row.get("skills_json") or "[]")
            row["slack_channels"] = json.loads(row.get("slack_channels_json") or "[]")
            out.append(row)
        return out

    def get_workforce_agent(self, tenant_id: str, agent_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workforce_agents WHERE tenant_id=? AND id=?",
                (tenant_id, agent_id),
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["skills"] = json.loads(out.get("skills_json") or "[]")
        out["slack_channels"] = json.loads(out.get("slack_channels_json") or "[]")
        return out

    def update_workforce_agent_status(self, tenant_id: str, agent_id: int, status: str) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "UPDATE workforce_agents SET status=?, updated_at=? WHERE tenant_id=? AND id=?",
                (status, datetime.utcnow().isoformat(), tenant_id, agent_id),
            )
            return cur.rowcount > 0

    def create_workforce_task(
        self,
        *,
        tenant_id: str,
        created_by: str,
        title: str,
        description: str,
        assignee_agent_id: int | None,
        collaborator_agent_ids: list[int] | None = None,
        priority: str = "medium",
        status: str = "open",
    ) -> int:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO workforce_tasks(
                    tenant_id, created_by, title, description, assignee_agent_id,
                    collaborator_agent_ids_json, priority, status, result_json,
                    created_at, updated_at
                ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    tenant_id,
                    created_by,
                    title,
                    description,
                    assignee_agent_id,
                    json.dumps(collaborator_agent_ids or []),
                    priority,
                    status,
                    None,
                    now,
                    now,
                ),
            )
            return int(cur.lastrowid)

    def list_workforce_tasks(self, tenant_id: str, status: str | None = None, limit: int = 200) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT * FROM workforce_tasks WHERE tenant_id=? AND status=? ORDER BY id DESC LIMIT ?",
                    (tenant_id, status, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM workforce_tasks WHERE tenant_id=? ORDER BY id DESC LIMIT ?",
                    (tenant_id, limit),
                ).fetchall()

        out: list[dict[str, Any]] = []
        for r in rows:
            row = dict(r)
            row["collaborator_agent_ids"] = json.loads(row.get("collaborator_agent_ids_json") or "[]")
            row["result"] = json.loads(row["result_json"]) if row.get("result_json") else None
            out.append(row)
        return out

    def get_workforce_task(self, tenant_id: str, task_id: int) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM workforce_tasks WHERE tenant_id=? AND id=?",
                (tenant_id, task_id),
            ).fetchone()
        if not row:
            return None
        out = dict(row)
        out["collaborator_agent_ids"] = json.loads(out.get("collaborator_agent_ids_json") or "[]")
        out["result"] = json.loads(out["result_json"]) if out.get("result_json") else None
        return out

    def update_workforce_task(
        self,
        *,
        tenant_id: str,
        task_id: int,
        status: str | None = None,
        assignee_agent_id: int | None = None,
        result: dict[str, Any] | None = None,
    ) -> bool:
        sets: list[str] = []
        values: list[Any] = []
        if status is not None:
            sets.append("status=?")
            values.append(status)
        if assignee_agent_id is not None:
            sets.append("assignee_agent_id=?")
            values.append(assignee_agent_id)
        if result is not None:
            sets.append("result_json=?")
            values.append(json.dumps(result))

        sets.append("updated_at=?")
        values.append(datetime.utcnow().isoformat())

        if not sets:
            return False

        values.extend([tenant_id, task_id])
        q = f"UPDATE workforce_tasks SET {', '.join(sets)} WHERE tenant_id=? AND id=?"
        with self._connect() as conn:
            cur = conn.execute(q, tuple(values))
            return cur.rowcount > 0
