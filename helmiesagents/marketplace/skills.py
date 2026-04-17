from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class SkillPackage:
    name: str
    version: str
    description: str
    content: str


def export_skill_package(path: str, package: SkillPackage) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(package.__dict__, indent=2))


def import_skill_package(path: str) -> SkillPackage:
    data: dict[str, Any] = json.loads(Path(path).read_text())
    return SkillPackage(**data)
