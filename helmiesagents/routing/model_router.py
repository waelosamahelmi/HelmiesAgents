from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import yaml


@dataclass
class ModelRoute:
    model: str | None
    policy_name: str


class ModelRouter:
    def __init__(self, default_model: str, policy_file: str | None = None) -> None:
        self.default_model = default_model
        self.rules: list[dict] = []
        if policy_file and Path(policy_file).exists():
            data = yaml.safe_load(Path(policy_file).read_text()) or {}
            self.rules = data.get("rules", [])

    def route(self, user_message: str) -> ModelRoute:
        text = user_message.lower()
        for rule in self.rules:
            keywords = [k.lower() for k in rule.get("keywords", [])]
            if keywords and any(k in text for k in keywords):
                return ModelRoute(model=rule.get("model"), policy_name=rule.get("name", "rule"))
        return ModelRoute(model=self.default_model, policy_name="default")
