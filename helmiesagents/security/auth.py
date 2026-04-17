from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any

import jwt

from helmiesagents.config import Settings
from helmiesagents.models import RequestContext


@dataclass
class AuthUser:
    username: str
    password_hash: str
    roles: list[str]
    tenant_id: str


def hash_password(password: str) -> str:
    return sha256(password.encode()).hexdigest()


class AuthService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.users = self._load_users(settings.auth_users_json)

    def _load_users(self, raw: str) -> dict[str, AuthUser]:
        items = json.loads(raw)
        out: dict[str, AuthUser] = {}
        for u in items:
            username = u["username"]
            pw = u.get("password", "")
            pw_hash = u.get("password_hash") or hash_password(pw)
            out[username] = AuthUser(
                username=username,
                password_hash=pw_hash,
                roles=u.get("roles", ["viewer"]),
                tenant_id=u.get("tenant_id", "default"),
            )
        return out

    def authenticate(self, username: str, password: str) -> RequestContext | None:
        user = self.users.get(username)
        if not user:
            return None
        if hash_password(password) != user.password_hash:
            return None
        return RequestContext(
            tenant_id=user.tenant_id,
            user_id=user.username,
            roles=user.roles,
            auto_approve=False,
        )

    def create_token(self, ctx: RequestContext, expires_hours: int = 24) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "sub": ctx.user_id,
            "tenant_id": ctx.tenant_id,
            "roles": ctx.roles,
            "auto_approve": ctx.auto_approve,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(hours=expires_hours)).timestamp()),
        }
        return jwt.encode(payload, self.settings.jwt_secret, algorithm="HS256")

    def decode_token(self, token: str) -> RequestContext:
        data: dict[str, Any] = jwt.decode(token, self.settings.jwt_secret, algorithms=["HS256"])
        return RequestContext(
            tenant_id=data.get("tenant_id", "default"),
            user_id=data.get("sub", "anonymous"),
            roles=data.get("roles", ["viewer"]),
            auto_approve=bool(data.get("auto_approve", False)),
        )
