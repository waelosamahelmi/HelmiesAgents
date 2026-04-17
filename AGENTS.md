# HelmiesAgents - Development Notes

## Principles

- deterministic where possible
- autonomous where useful
- memory-driven compounding
- strict execution logs for trust

## Runbook

```bash
pip install -e .[dev]
pytest -q
helmiesagents serve
```

## Next Improvements

- async task queue + background workers
- gateway implementations
- model routing and policy engine
