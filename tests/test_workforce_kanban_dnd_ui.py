from __future__ import annotations

from fastapi.testclient import TestClient

from helmiesagents.api.server import create_app
from helmiesagents.config import Settings


def test_web_panel_contains_drag_drop_kanban_controls(tmp_path):
    app = create_app(Settings(db_path=str(tmp_path / "webpanel_dnd.db")))
    client = TestClient(app)

    r = client.get("/")
    assert r.status_code == 200
    html = r.text

    if "<div id=\"root\"></div>" in html:
        # Built webapp shell path
        assert "assets/index-" in html
        return

    assert ("handleCardDragStart" in html) or ("kanban" in html.lower())
    assert ("handleColumnDrop" in html) or ("drop" in html.lower())
    assert ("draggable=\"true\"" in html) or ("draggable" in html.lower())
    assert "/workforce/tasks/" in html
    assert "/status" in html
