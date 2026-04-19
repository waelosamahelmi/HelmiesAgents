# HelmiesAgents Detailed TODO

## Phase 1 - Foundation

- [x] Core repository bootstrap
- [x] Agent loop implementation
- [x] Tool registry and built-in tools
- [x] Memory store with searchable history
- [x] Skill persistence API
- [x] Workflow DAG engine
- [x] FastAPI service
- [x] CLI with REPL and commands
- [x] Basic web chat UI
- [x] Test suite for core modules

## Phase 2 - Capability Hardening

- [x] async tool/workflow execution with cancellation
- [x] policy-driven approval gates
- [x] workflow persistence and status tracking
- [x] richer context compression
- [x] per-user and per-tenant memory scopes
- [x] model routing policy support

## Phase 3 - Platform Expansion

- [x] Slack adapter implementation
- [x] Telegram adapter implementation
- [x] WhatsApp adapter implementation
- [x] Discord adapter implementation
- [x] auth endpoints with role-aware access
- [x] gateway inbound routing endpoint

## Phase 4 - Competitive Features

- [x] benchmark harness (SWE-style lightweight)
- [x] skill marketplace package import/export
- [x] benchmark result persistence
- [x] regression-friendly benchmark listing API
- [x] model routing policy engine

## Phase 5 - Enterprise Readiness

- [x] audit log table and APIs
- [x] audit export utility
- [x] tenant isolation in persistence
- [x] SCIM-like user provisioning endpoints
- [x] secrets vault integration (encrypted at rest)
- [x] deployment blueprints doc

## Next frontier (post all-phases)

- [x] true websocket streaming responses
- [x] distributed task queue (Celery/Arq/RQ)
- [x] SSO/SAML/OIDC enterprise login
- [x] policy-as-code DSL
- [x] advanced eval suites and CI quality gates
- [x] autonomous critic-repair quality loop
- [x] autonomous task decomposition + self-verification subruns
- [x] policy-aware execution budgets (role/tenant caps)
- [x] web budget panel (effective budget visibility)

## Workforce / Team-Mode Expansion

- [x] Role + CV based agent profile suggestion endpoint
- [x] Hire-agent endpoint and DB persistence for agent workforce records
- [x] Slack manifest generator endpoint for hired agents
- [x] Workforce task model (assignee + collaborator agents)
- [x] Run-task endpoint with collaborator notes + synthesis
- [x] Web UI controls for workforce management
- [x] API tests for workforce flows

## Next Targets (not yet complete)

- [x] Slack inbound mention -> route to specific hired agent persona
- [x] Agent-to-agent message bus with conversation thread IDs
- [x] Workforce Kanban board (control-center panel) + status-oriented task lanes
- [x] Real scheduler for recurring workforce tasks (API + persistence + manual tick)
- [x] Optional per-agent model/provider settings
- [x] Full admin WebUI migration scaffold with API-integrated control center (React webapp + auto-serve dist fallback from API)
- [x] Slack manifest installer wizard + OAuth callback automation (backend + persistence)
