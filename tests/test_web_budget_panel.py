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

    if "<div id=\"root\"></div>" in html:
        # Built webapp shell path
        assert "assets/index-" in html
        return

    assert ("loadBudget()" in html) or ('data-testid="budget-panel"' in html)
    assert "Effective Budget" in html
    assert "/execution/budget/effective" in html
    assert ('id="budget"' in html) or ('data-testid="budget-panel"' in html)
    assert ("Workforce (Agent Teams)" in html) or ("Workforce Control Center" in html)
    assert "/workforce/suggest" in html
    assert "/workforce/manifest/slack" in html
    assert ("workforceRunTask()" in html) or ("Run Task" in html)
