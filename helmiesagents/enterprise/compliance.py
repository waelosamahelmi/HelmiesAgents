from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from helmiesagents.memory.store import MemoryStore


def export_audit_logs(memory: MemoryStore, tenant_id: str, out_path: str, limit: int = 500) -> dict[str, Any]:
    rows = memory.list_audit(tenant_id=tenant_id, limit=limit)
    p = Path(out_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(rows, indent=2))
    return {"path": str(p), "rows": len(rows)}
