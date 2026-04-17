from __future__ import annotations

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
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS facts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(category, key)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS skills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_message(self, session_id: str, role: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO messages(session_id, role, content, created_at) VALUES(?,?,?,?)",
                (session_id, role, content, datetime.utcnow().isoformat()),
            )

    def get_recent_messages(self, session_id: str, limit: int = 20) -> list[MemoryHit]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, role, content, created_at FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?",
                (session_id, limit),
            ).fetchall()
        return [MemoryHit(**dict(r)) for r in reversed(rows)]

    def search_messages(self, query: str, limit: int = 10) -> list[MemoryHit]:
        like = f"%{query}%"
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id, role, content, created_at FROM messages WHERE content LIKE ? ORDER BY id DESC LIMIT ?",
                (like, limit),
            ).fetchall()
        return [MemoryHit(**dict(r)) for r in rows]

    def upsert_fact(self, category: str, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO facts(category, key, value, updated_at)
                VALUES(?,?,?,?)
                ON CONFLICT(category, key) DO UPDATE SET
                  value=excluded.value,
                  updated_at=excluded.updated_at
                """,
                (category, key, value, datetime.utcnow().isoformat()),
            )

    def list_facts(self, category: str | None = None) -> list[dict[str, Any]]:
        with self._connect() as conn:
            if category:
                rows = conn.execute(
                    "SELECT category, key, value, updated_at FROM facts WHERE category=? ORDER BY updated_at DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT category, key, value, updated_at FROM facts ORDER BY updated_at DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def save_skill(self, name: str, description: str, content: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO skills(name, description, content, created_at)
                VALUES(?,?,?,?)
                ON CONFLICT(name) DO UPDATE SET
                    description=excluded.description,
                    content=excluded.content
                """,
                (name, description, content, datetime.utcnow().isoformat()),
            )

    def list_skills(self) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT name, description, created_at FROM skills ORDER BY name ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_skill(self, name: str) -> dict[str, Any] | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT name, description, content, created_at FROM skills WHERE name=?",
                (name,),
            ).fetchone()
        return dict(row) if row else None
