from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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

    # auth + tenancy
    jwt_secret: str = "change-me-dev-secret"
    auth_users_json: str = '[{"username":"admin","password": "admin123","roles":["admin"],"tenant_id":"default"}]'

    # optional routing policy file
    routing_policy_file: str | None = None

    # optional policy-as-code DSL file
    policy_dsl_file: str | None = None

    # queue backend
    queue_backend: str = "memory"  # memory | sqlite
    queue_autostart_worker: bool = True
    queue_poll_interval_seconds: float = 0.5

    # eval suites
    eval_suites_file: str | None = None
    eval_min_score: float = 80.0

    # autonomous quality critic loop
    critic_enabled: bool = True
    critic_max_retries: int = 1
    critic_min_score: float = 0.7

    # autonomous decomposition + subruns
    autonomous_subruns_enabled: bool = True
    autonomous_subruns_max: int = 2
    autonomous_subruns_verify: bool = True

    # policy-aware execution budgets
    execution_budget_file: str | None = None

    # gateway credentials
    slack_bot_token: str | None = None
    telegram_bot_token: str | None = None
    discord_bot_token: str | None = None
    whatsapp_api_url: str | None = None
    whatsapp_token: str | None = None

    # scim
    scim_token: str = "change-me-scim-token"

    # secrets vault
    vault_key: str | None = None

    # sso
    sso_enabled: bool = False
    sso_oidc_issuer: str | None = None
    sso_oidc_audience: str | None = None
    sso_oidc_jwt_secret: str | None = None
    sso_saml_expected_issuer: str | None = None

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
            jwt_secret=os.getenv("HELMIES_JWT_SECRET", "change-me-dev-secret"),
            auth_users_json=os.getenv(
                "HELMIES_AUTH_USERS_JSON",
                '[{"username":"admin","password": "admin123","roles":["admin"],"tenant_id":"default"}]',
            ),
            routing_policy_file=os.getenv("HELMIES_ROUTING_POLICY_FILE"),
            policy_dsl_file=os.getenv("HELMIES_POLICY_DSL_FILE"),
            queue_backend=os.getenv("HELMIES_QUEUE_BACKEND", "memory"),
            queue_autostart_worker=_env_bool("HELMIES_QUEUE_AUTOSTART_WORKER", True),
            queue_poll_interval_seconds=float(os.getenv("HELMIES_QUEUE_POLL_INTERVAL_SECONDS", "0.5")),
            eval_suites_file=os.getenv("HELMIES_EVAL_SUITES_FILE"),
            eval_min_score=float(os.getenv("HELMIES_EVAL_MIN_SCORE", "80")),
            critic_enabled=_env_bool("HELMIES_CRITIC_ENABLED", True),
            critic_max_retries=int(os.getenv("HELMIES_CRITIC_MAX_RETRIES", "1")),
            critic_min_score=float(os.getenv("HELMIES_CRITIC_MIN_SCORE", "0.7")),
            autonomous_subruns_enabled=_env_bool("HELMIES_AUTONOMOUS_SUBRUNS_ENABLED", True),
            autonomous_subruns_max=int(os.getenv("HELMIES_AUTONOMOUS_SUBRUNS_MAX", "2")),
            autonomous_subruns_verify=_env_bool("HELMIES_AUTONOMOUS_SUBRUNS_VERIFY", True),
            execution_budget_file=os.getenv("HELMIES_EXECUTION_BUDGET_FILE"),
            slack_bot_token=os.getenv("SLACK_BOT_TOKEN"),
            telegram_bot_token=os.getenv("TELEGRAM_BOT_TOKEN"),
            discord_bot_token=os.getenv("DISCORD_BOT_TOKEN"),
            whatsapp_api_url=os.getenv("WHATSAPP_API_URL"),
            whatsapp_token=os.getenv("WHATSAPP_TOKEN"),
            scim_token=os.getenv("HELMIES_SCIM_TOKEN", "change-me-scim-token"),
            vault_key=os.getenv("HELMIES_VAULT_KEY"),
            sso_enabled=_env_bool("HELMIES_SSO_ENABLED", False),
            sso_oidc_issuer=os.getenv("HELMIES_SSO_OIDC_ISSUER"),
            sso_oidc_audience=os.getenv("HELMIES_SSO_OIDC_AUDIENCE"),
            sso_oidc_jwt_secret=os.getenv("HELMIES_SSO_OIDC_JWT_SECRET"),
            sso_saml_expected_issuer=os.getenv("HELMIES_SSO_SAML_EXPECTED_ISSUER"),
        )

    def ensure_dirs(self) -> None:
        Path(self.workspace_dir).mkdir(parents=True, exist_ok=True)
