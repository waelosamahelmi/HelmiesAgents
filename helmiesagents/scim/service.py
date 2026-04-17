from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from helmiesagents.memory.store import MemoryStore


@dataclass
class ScimUser:
    tenant_id: str
    username: str
    password: str
    roles: list[str]


def _hash(v: str) -> str:
    return sha256(v.encode()).hexdigest()


class ScimService:
    def __init__(self, memory: MemoryStore) -> None:
        self.memory = memory

    def create_or_update_user(self, u: ScimUser) -> None:
        # minimal SCIM-like persistence using users table
        with self.memory._connect() as conn:
            conn.execute(
                """
                INSERT INTO users(tenant_id, username, password_hash, roles, created_at)
                VALUES(?,?,?,?,datetime('now'))
                ON CONFLICT(tenant_id, username) DO UPDATE SET
                    password_hash=excluded.password_hash,
                    roles=excluded.roles
                """,
                (u.tenant_id, u.username, _hash(u.password), ",".join(u.roles)),
            )

    def list_users(self, tenant_id: str) -> list[dict]:
        with self.memory._connect() as conn:
            rows = conn.execute(
                "SELECT tenant_id, username, roles, created_at FROM users WHERE tenant_id=? ORDER BY username",
                (tenant_id,),
            ).fetchall()
        return [dict(r) for r in rows]
