# HelmiesAgents

HelmiesAgents is an open agent platform built to compete with modern AI agent systems by combining:

- long-horizon autonomous execution
- deterministic workflow orchestration
- compounding memory + reusable skills
- multi-surface delivery (CLI, API, Web, gateways)

It is designed for real work, not just demo loops.

## Vision

Most agent stacks optimize one dimension:
- autonomy without control, or
- control without adaptability, or
- UX without durable memory.

HelmiesAgents combines all three:

1) Autonomous: can plan, execute, reflect, and reuse patterns.
2) Deterministic: can run structured DAG workflows with dependency control.
3) Operational: can be used from terminal, browser, and messaging surfaces.

## What is implemented now

### Agent Runtime
- Core agent loop with provider abstraction
- Plan generation before response
- Tool-call parser and execution bridge
- Built-in safety-aware shell execution

### Memory and Skills
- SQLite-backed message history
- Searchable memory retrieval
- Facts store (upsert/list)
- Skills store (save/list/get)

### Tooling
Built-in tools:
- `time_now`
- `read_file`
- `write_file`
- `search_files`
- `run_shell`
- `http_get`
- `memory_search`
- `ingest_to_markdown`

### Workflows
- YAML DAG engine with dependencies
- Node types:
  - `prompt`
  - `shell`
  - `python`
  - `http`
- CLI and API workflow execution

### Interfaces
- CLI (`helmiesagents`)
- FastAPI server
- Browser chat UI (`/`)
- Gateway router abstraction (Slack/Telegram/WhatsApp/Discord adapters scaffolded)

## Competitive design basis

This build was planned after studying 20 repositories including:

- GenericAgent
- claude-mem
- superpowers
- open-agents
- hermes-agent
- multica
- Archon
- deer-flow
- markitdown
- and 11 more

Full notes: `docs/REPO_STUDY_FULL.md` and `docs/COMPETITIVE_ANALYSIS.md`.

## Quickstart

```bash
cd HelmiesAgents
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]

pytest -q

helmiesagents serve --host 0.0.0.0 --port 8787
```

Open `http://localhost:8787`.

### CLI examples

```bash
# one-shot chat
helmiesagents chat "Create a launch checklist for HelmiesAgents"

# interactive chat
helmiesagents repl

# run workflow
helmiesagents run-workflow examples/workflows/research_and_report.yaml

# initialize local workspace template
helmiesagents init-project ./my_workspace

# search memory
helmiesagents memory-search "launch"
```

## API examples

### Health

```bash
curl http://localhost:8787/health
```

### Chat

```bash
curl -X POST http://localhost:8787/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"demo","message":"what time is it"}'
```

### Run workflow

```bash
curl -X POST http://localhost:8787/workflow/run \
  -H 'Content-Type: application/json' \
  -d '{"workflow_path":"examples/workflows/research_and_report.yaml","session_id":"wf1"}'
```

## Environment variables

Optional OpenAI-compatible provider:

- `HELMIES_PROVIDER=openai`
- `OPENAI_API_KEY=...`
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_MODEL=gpt-4o-mini`

Runtime settings:

- `HELMIES_DB_PATH=./helmiesagents.db`
- `HELMIES_WORKSPACE_DIR=./workspace`
- `HELMIES_HOST=0.0.0.0`
- `HELMIES_PORT=8787`

Without provider keys, the runtime uses a deterministic local mock provider for offline development/testing.

## Project structure

```text
helmiesagents/
  core/         # agent loop + planner
  providers/    # model provider adapters
  tools/        # tool registry + built-ins
  memory/       # sqlite memory and skills
  workflow/     # yaml DAG runtime
  api/          # fastapi server
  web/          # lightweight web UI
  gateways/     # platform adapters + router
```

## Documentation

- `docs/VISION.md`
- `docs/ARCHITECTURE.md`
- `docs/DIRECTIONS.md`
- `docs/COMPETITIVE_ANALYSIS.md`
- `docs/REPO_STUDY_FULL.md`
- `docs/TODO_DETAILED.md`

## Roadmap

Near-term priorities:

1) full Slack/Telegram/WhatsApp/Discord gateway implementations
2) richer approval + policy system for risky actions
3) async queue and resumable run manager
4) benchmark harness and quality scoring
5) multi-tenant SaaS packaging

## License

MIT
