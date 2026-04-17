# HelmiesAgents Architecture

## System overview

HelmiesAgents follows a layered architecture:

1. Interfaces
   - CLI
   - Web UI
   - HTTP API
   - Gateway adapters

2. Agent Core
   - planner
   - policy router
   - provider abstraction
   - tool executor

3. Execution Engine
   - workflow DAG runtime
   - node evaluators (prompt/shell/python/http)

4. Knowledge Layer
   - memory store
   - session archive
   - skill store

5. Integrations
   - model providers
   - external APIs
   - messaging platforms

## Core loop

1. Receive request
2. Retrieve memory context
3. Build plan
4. Execute tools/workflow nodes
5. Validate outputs
6. Write memory and skill deltas
7. Return final answer with trace

## Memory model

- Session memory: conversational logs and artifacts
- Fact memory: stable facts/preferences
- Skill memory: reusable procedures
- Run memory: workflow execution logs

## Workflow model

YAML-defined DAG:

- `prompt` node: agent reasoning/action
- `shell` node: deterministic command execution
- `python` node: script execution
- `http` node: API calls

Each node supports:
- dependencies
- timeout
- retry policy (planned)
- output capture

## Safety model

- command-level safety policy (allow/deny patterns)
- explicit external action boundaries
- immutable run logs for audit

## Extensibility

- Register custom tools in `helmiesagents/tools/registry.py`
- Add providers via `helmiesagents/providers/`
- Add adapters via `helmiesagents/gateways/`

## Planned architecture upgrades

- distributed execution queue
- role-specialized subagents
- vector retrieval augmentation
- tenant isolation and policy sandboxing
