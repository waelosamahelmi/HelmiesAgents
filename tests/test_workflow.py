from pathlib import Path

from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.workflow.engine import WorkflowEngine


def test_workflow_runs(tmp_path):
    settings = Settings(db_path=str(tmp_path / "wf.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)
    engine = WorkflowEngine(agent=agent)

    wf = tmp_path / "wf.yaml"
    wf.write_text(
        """
name: test
nodes:
  - id: a
    type: prompt
    prompt: "say hello"
  - id: b
    type: shell
    depends_on: [a]
    command: "echo done"
""".strip()
    )

    res = engine.run(str(wf), session_id="wf-test")
    assert res.status == "success"
    assert "a" in res.outputs
    assert "b" in res.outputs
