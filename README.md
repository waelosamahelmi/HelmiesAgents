# HelmiesAgents

HelmiesAgents is a production-minded, open AI agent framework designed to compete with modern agent stacks by combining:

- deterministic workflow orchestration (Archon-style)
- self-evolving skills and memory (GenericAgent + claude-mem style)
- multi-surface execution (CLI, API, Web UI, and gateway adapters)
- strong tool runtime with auditability and safety controls

## Why HelmiesAgents

Most agent projects optimize one axis only: either autonomy, or reliability, or UX.
HelmiesAgents is designed for all three:

1. Autonomous enough to execute long-horizon tasks
2. Deterministic enough to be trusted in business workflows
3. Extensible enough to become your team’s operating system

## Core capabilities

- Agent loop with tool execution and memory writeback
- SQLite-based long-term memory + searchable session history
- Skills store with reusable procedures
- YAML workflow engine with dependency graph execution
- FastAPI server for chat + workflow runs
- Browser-based chat UI
- CLI with REPL, chat, workflow, and service commands
- Gateway adapter interfaces for Slack/Telegram/WhatsApp/Discord

## Quickstart

```bash
cd HelmiesAgents
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

# run tests
pytest -q

# run web/api server
helmiesagents serve --host 0.0.0.0 --port 8787

# chat from terminal
helmiesagents chat "Plan a weekly product launch workflow"
```

Open: `http://localhost:8787`

## Environment variables

Optional OpenAI-compatible provider support:

- `HELMIES_PROVIDER=openai`
- `OPENAI_API_KEY=...`
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_MODEL=gpt-4o-mini`

Without keys, HelmiesAgents runs with a deterministic local fallback provider for offline development.

## Project docs

- `docs/VISION.md`
- `docs/ARCHITECTURE.md`
- `docs/COMPETITIVE_ANALYSIS.md`
- `docs/TODO_DETAILED.md`

## License

MIT
