# Deployment Blueprints

## 1) Local single-node (dev / solo)

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
helmiesagents serve --host 0.0.0.0 --port 8787
```

## 2) Docker container (simple prod)

Dockerfile:
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .
EXPOSE 8787
CMD ["helmiesagents","serve","--host","0.0.0.0","--port","8787"]
```

## 3) Reverse proxy + TLS
- Nginx/Caddy in front of FastAPI
- enforce HTTPS
- restrict /scim and /vault endpoints by IP + token

## 4) Multi-tenant managed mode
- Shared API service
- Tenant-scoped DB records
- JWT auth with tenant claims
- Dedicated encryption key management

## 5) Enterprise hardening checklist
- strong JWT secret
- rotate SCIM token
- set HELMIES_VAULT_KEY
- configure log shipping
- nightly audit export
