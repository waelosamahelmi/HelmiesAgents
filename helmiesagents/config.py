from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


@dataclass
class Settings:
    provider: str = "auto"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    db_path: str = "./helmiesagents.db"
    workspace_dir: str = "./workspace"

    host: str = "0.0.0.0"
    port: int = 8787

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            provider=os.getenv("HELMIES_PROVIDER", "auto"),
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            db_path=os.getenv("HELMIES_DB_PATH", "./helmiesagents.db"),
            workspace_dir=os.getenv("HELMIES_WORKSPACE_DIR", "./workspace"),
            host=os.getenv("HELMIES_HOST", "0.0.0.0"),
            port=int(os.getenv("HELMIES_PORT", "8787")),
        )

    def ensure_dirs(self) -> None:
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
