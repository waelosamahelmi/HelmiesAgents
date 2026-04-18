# HelmiesAgents

HelmiesAgents is a competitive open AI agent platform built for real execution:

- autonomous agent loop
- deterministic workflow DAG runtime
- memory + skills compounding system
- API + CLI + Web interfaces
- gateway integrations
- benchmark and enterprise controls

## Repo

https://github.com/waelosamahelmi/HelmiesAgents

## What is done (All Phases)

### Phase 1 — Foundation
- agent loop + provider abstraction
- tool registry + built-in tools
- sqlite memory + skills
- workflow engine
- fastapi api
- cli + web ui

### Phase 2 — Hardening
- async workflow execution + cancellation
- policy-driven approval checks
- context compression
- per-user/per-tenant memory scope
- model routing policy

### Phase 3 — Platform Expansion
- slack / telegram / discord / whatsapp send adapters
- unified gateway inbound routing endpoint
- role-aware auth and JWT login

### Phase 4 — Competitive Features
- benchmark harness + persistent benchmark results
- skill package import/export marketplace format
- route policy evaluation

### Phase 5 — Enterprise Readiness
- audit logging and export API
- scim-like user provisioning endpoints
- encrypted secrets vault integration
- deployment blueprints documentation

## Quickstart

```bash
cd HelmiesAgents
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
pytest -q
helmiesagents serve --host 0.0.0.0 --port 8787
```

Open http://localhost:8787

### Default login
- username: `admin`
- password: `admin123`

Change this immediately via `HELMIES_AUTH_USERS_JSON` in production.

## Key API Endpoints

### Auth
- `POST /auth/login`
- `POST /auth/sso/oidc`
- `POST /auth/sso/saml`

### Agent
- `POST /chat`
- `WS /chat/ws` (true token streaming + final tool-executed response event)
- `GET /memory/search`

### Skills
- `GET /skills`
- `POST /skills`
- `POST /skills/export`
- `POST /skills/import`

### Workflow
- `POST /workflow/run`
- `POST /workflow/run_async`
- `GET /workflow/job/{job_id}`
- `POST /workflow/job/{job_id}/cancel`
- `GET /workflow/jobs` (queue backlog/status view)
- `POST /workflow/worker/run_once` (manual worker tick for sqlite queue)
- `GET /workflow/runs`

### Gateways
- `POST /gateway/send`
- `POST /gateway/inbound`

### Approvals
- `POST /approvals/check`
- `POST /approvals/decide`

### Benchmark
- `POST /benchmark/run`
- `GET /benchmark/results`

### Enterprise
- `GET /audit/logs`
- `POST /audit/export`
- `POST /scim/users`
- `GET /scim/users`
- `POST /vault/secrets`
- `GET /vault/secrets/{key}`

## CLI Commands

```bash
helmiesagents chat "what time is it"
helmiesagents repl
helmiesagents run-workflow examples/workflows/research_and_report.yaml
helmiesagents run-workflow-async examples/workflows/research_and_report.yaml
helmiesagents benchmark-run --suite smoke
helmiesagents benchmark-list --suite smoke
helmiesagents audit-export ./out/audit.json
helmiesagents init-project ./my_workspace
```

## Environment Variables

### Core
- `HELMIES_PROVIDER=auto|openai`
- `OPENAI_API_KEY=***
- `OPENAI_BASE_URL=https://api.openai.com/v1`
- `OPENAI_MODEL=gpt-4o-mini`
- `HELMIES_DB_PATH=./helmiesagents.db`
- `HELMIES_WORKSPACE_DIR=./workspace`
- `HELMIES_ROUTING_POLICY_FILE=./routing_policy.yaml`
- `HELMIES_QUEUE_BACKEND=memory|sqlite` (default: `memory`)
- `HELMIES_QUEUE_AUTOSTART_WORKER=true|false` (default: `true`)
- `HELMIES_QUEUE_POLL_INTERVAL_SECONDS=0.5`

### Auth / Enterprise
- `HELMIES_JWT_SECRET=***`
- `HELMIES_AUTH_USERS_JSON='[{"username":"admin","password":"admin123","roles":["admin"],"tenant_id":"default"}]'`
- `HELMIES_SCIM_TOKEN=change-me-scim-token`
- `HELMIES_VAULT_KEY=change-me-vault-key`
- `HELMIES_SSO_ENABLED=true|false`
- `HELMIES_SSO_OIDC_ISSUER=https://idp.example.com`
- `HELMIES_SSO_OIDC_AUDIENCE=helmiesagents`
- `HELMIES_SSO_OIDC_JWT_SECRET=***`
- `HELMIES_SSO_SAML_EXPECTED_ISSUER=urn:test:idp`

### Gateways
- `SLACK_BOT_TOKEN=...`
- `TELEGRAM_BOT_TOKEN=...`
- `DISCORD_BOT_TOKEN=...`
- `WHATSAPP_API_URL=...`
- `WHATSAPP_TOKEN=...`

## Docs

- `docs/VISION.md`
- `docs/ARCHITECTURE.md`
- `docs/DIRECTIONS.md`
- `docs/COMPETITIVE_ANALYSIS.md`
- `docs/REPO_STUDY_FULL.md`
- `docs/TODO_DETAILED.md`
- `docs/DEPLOYMENT_BLUEPRINTS.md`
- `docs/PHASES_COMPLETION_REPORT.md`

## License

MIT
