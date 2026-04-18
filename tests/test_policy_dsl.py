import yaml

from helmiesagents.config import Settings
from helmiesagents.security.policy import PolicyEngine


def test_policy_dsl_precedence_and_override(tmp_path):
    policy_file = tmp_path / "policy.dsl.yaml"
    policy_file.write_text(
        yaml.safe_dump(
            {
                "version": 1,
                "rules": [
                    {
                        "name": "allow-safe-write",
                        "effect": "allow",
                        "tool": "write_file",
                        "when": {"path_prefix": "/opt/safe/"},
                    },
                    {
                        "name": "approve-docker",
                        "effect": "approve",
                        "tool": "run_shell",
                        "when": {"command_regex": r"^docker\s+"},
                    },
                    {
                        "name": "deny-docker-rm-force",
                        "effect": "deny",
                        "tool": "run_shell",
                        "when": {"command_regex": r"^docker\s+rm\s+-f\b"},
                    },
                ],
            }
        )
    )

    policy = PolicyEngine(policy_file=str(policy_file))

    deny = policy.evaluate("run_shell", {"command": "docker rm -f deadbeef"})
    assert deny.blocked is True
    assert deny.requires_approval is True
    assert deny.effect == "deny"
    assert deny.rule_name == "deny-docker-rm-force"

    approve = policy.evaluate("run_shell", {"command": "docker build ."})
    assert approve.blocked is False
    assert approve.requires_approval is True
    assert approve.effect == "approve"
    assert approve.rule_name == "approve-docker"

    allow = policy.evaluate("write_file", {"path": "/opt/safe/notes.txt"})
    assert allow.blocked is False
    assert allow.requires_approval is False
    assert allow.effect == "allow"
    assert allow.rule_name == "allow-safe-write"

    # no DSL match -> fallback to built-in policy
    builtin = policy.evaluate("run_shell", {"command": "sudo whoami"})
    assert builtin.requires_approval is True
    assert builtin.effect == "approve"


def test_policy_dsl_settings_from_env(monkeypatch):
    monkeypatch.setenv("HELMIES_POLICY_DSL_FILE", "/tmp/policy.dsl.yaml")
    settings = Settings.from_env()
    assert settings.policy_dsl_file == "/tmp/policy.dsl.yaml"


def test_policy_dsl_invalid_file_falls_back_to_builtin(tmp_path):
    policy_file = tmp_path / "broken.dsl.yaml"
    policy_file.write_text("rules: [:::invalid")

    policy = PolicyEngine(policy_file=str(policy_file))
    decision = policy.evaluate("run_shell", {"command": "sudo whoami"})
    assert decision.requires_approval is True
    assert decision.effect == "approve"
