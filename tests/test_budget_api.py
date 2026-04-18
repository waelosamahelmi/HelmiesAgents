from __future__ import annotations

import yaml
from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def _settings(tmp_path, *, budget_file: str) -> Settings:
    return Settings(
        db_path=str(tmp_path / "api_budget.db"),
        execution_budget_file=budget_file,
        auth_users_json='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]',
        jwt_secret="a" * 40,
    )


def test_budget_effective_endpoint_and_chat_quality_budget(tmp_path):
    policy = tmp_path / "policy.execution.yaml"
    policy.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "defaults": {"max_tool_calls": 5, "max_subruns": 2, "max_critic_retries": 1},
                "roles": {"admin": {"max_tool_calls": 9}, "viewer": {"max_tool_calls": 1}},
                "tenants": {"default": {"max_subruns": 4}},
            }
        )
    )

    app = create_app(_settings(tmp_path, budget_file=str(policy)))
    client = TestClient(app)

    login = client.post("/auth/login", json={"username": "admin", "password": "admin123"})
    assert login.status_code == 200
    token = login.json()["access_token"]

    b = client.get("/execution/budget/effective", headers={"Authorization": f"Bearer {token}"})
    assert b.status_code == 200
    body = b.json()
    assert body["tenant_id"] == "default"
    assert body["roles"] == ["admin"]
    assert body["budget"]["max_tool_calls"] == 9
    assert body["budget"]["max_subruns"] == 4
    assert body["budget"]["max_critic_retries"] == 1

    chat = client.post(
        "/chat",
        headers={"Authorization": f"Bearer {token}"},
        json={"session_id": "s1", "message": "what time is it"},
    )
    assert chat.status_code == 200
    q = chat.json()["quality"]
    assert q["budget"]["max_tool_calls"] == 9


def test_budget_effective_defaults_when_not_configured(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "api_budget_none.db")))
    client = TestClient(app)

    r = client.get("/execution/budget/effective")
    assert r.status_code == 200
    body = r.json()
    assert body["tenant_id"] == "default"
    assert body["roles"] == ["viewer"]
    assert body["budget"]["max_tool_calls"] is None
    assert body["budget"]["max_subruns"] is None
    assert body["budget"]["max_critic_retries"] is None
