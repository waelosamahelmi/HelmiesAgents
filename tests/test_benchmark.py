from helmiesagents.config import Settings
from helmiesagents.memory.store import MemoryStore
from helmiesagents.tools.registry import ToolRegistry
from helmiesagents.tools.builtin import install_builtin_tools
from helmiesagents.core.agent import HelmiesAgent
from helmiesagents.benchmark.harness import BenchmarkHarness, BenchmarkScenario
from helmiesagents.models import RequestContext


def test_benchmark_suite(tmp_path):
    settings = Settings(db_path=str(tmp_path / "bench.db"))
    memory = MemoryStore(settings.db_path)
    reg = ToolRegistry()
    install_builtin_tools(reg, memory)
    agent = HelmiesAgent(settings=settings, memory=memory, tools=reg)
    harness = BenchmarkHarness(agent, memory)

    summary = harness.run_suite(
        RequestContext(tenant_id='default', user_id='u1', roles=['admin']),
        'smoke',
        [
            BenchmarkScenario(name='time', prompt='what time is it', must_contain=['time']),
            BenchmarkScenario(name='files', prompt='list files', must_contain=['files'])
        ]
    )

    assert summary.total == 2
    assert summary.passed >= 1
