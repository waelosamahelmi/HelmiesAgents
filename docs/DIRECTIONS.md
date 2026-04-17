# HelmiesAgents Directions (Execution Blueprint)

## Product direction

HelmiesAgents is not only a chat assistant. It is an execution platform:

- chat loop for interaction
- workflow graph for deterministic automation
- memory + skills for compounding intelligence
- gateway bridge for operational usage in team channels

## Build directions

1) Keep the core loop minimal and auditable.
2) Move complexity to pluggable modules (tools/providers/gateways).
3) Prefer deterministic nodes when possible to reduce cost and failure rate.
4) Treat memory as a first-class system, not a plugin.
5) Build UI and CLI around the same API contracts.

## Technical directions

- Python core runtime
- SQLite default persistence, Postgres-ready schema strategy
- OpenAI-compatible provider adapter interface
- FastAPI-first backend
- YAML workflows with future visual editor parity

## Commercial directions

- self-hosted-first for cost control
- managed cloud edition as premium
- org memory and skills as strategic lock-in
- benchmark-backed quality claims

## Differentiation directions

- stronger deterministic harness than pure chat agents
- stronger memory and skill compounding than pure workflow engines
- stronger operational UX than pure SDK/toolkit repos
