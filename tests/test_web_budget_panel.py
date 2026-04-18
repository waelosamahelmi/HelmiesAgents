from __future__ import annotations

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def test_web_panel_contains_budget_controls_and_render_target(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "webpanel.db")))
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200
    html = r.text

    assert "loadBudget()" in html
    assert "Effective Budget" in html
    assert "/execution/budget/effective" in html
    assert "id=\"budget\"" in html
