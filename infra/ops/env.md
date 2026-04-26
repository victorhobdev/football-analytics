# Environment and secret contract

This file documents the runtime configuration contract. Real secrets must live in the local `.env` file, shell environment, CI secret store, or production secret manager. They must not be committed.

## Runtime classes

Public values:
- `NEXT_PUBLIC_BFF_BASE_URL`
- Non-sensitive IDs such as default league and season selectors.

Private configuration:
- `ENVIRONMENT`
- `BFF_*` runtime settings
- `POSTGRES_USER`, `POSTGRES_DB`, `POSTGRES_HOST`, `POSTGRES_PORT`
- Provider base URLs and ingest rate settings.

Secrets:
- `POSTGRES_PASSWORD`
- `FOOTBALL_PG_DSN`, `DATABASE_URL`
- `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`
- `AIRFLOW__DATABASE__SQL_ALCHEMY_CONN`
- `AIRFLOW__CORE__FERNET_KEY`
- `AIRFLOW__WEBSERVER__SECRET_KEY`
- `AIRFLOW_ADMIN_PASSWORD`
- `APIFOOTBALL_API_KEY`
- `API_KEY_SPORTMONKS`

## Local compose behavior

`docker-compose.yml` uses Compose secrets for service-level sensitive values. In local development, Compose reads those secrets from the host environment or the project `.env` file and mounts them under `/run/secrets/*` inside containers.

The local `.env` file remains ignored by Git. Use `infra/env.example` as the sanitized template and replace every `change_me_*` value before starting the stack.

For local Compose, keep optional provider keys present even when unused. Use an empty value such as `API_KEY_SPORTMONKS=` if that provider is not active.

## BFF hardening knobs

Production defaults should use:

```env
ENVIRONMENT=production
BFF_EXPOSE_API_DOCS=false
BFF_CORS_ALLOW_ORIGINS=https://your-public-frontend.example
BFF_CORS_ALLOW_CREDENTIALS=false
BFF_RATE_LIMIT_ENABLED=true
BFF_RATE_LIMIT_TRUST_PROXY_HEADERS=true
```

Keep `BFF_CORS_ALLOW_CREDENTIALS=false` unless the public API starts using cookies or browser credentials. If credentials are enabled, origins, methods and headers must remain explicit.

## Rotation

Rotate immediately if any secret appears in logs, issue comments, screenshots, CI output, or Git history. After rotation, restart the affected service and run a smoke test:

```bash
docker compose ps
curl -f http://127.0.0.1:8000/health
docker compose logs --tail=100 airflow-scheduler
```

## Frontend rule

Only values intended for the browser may use the `NEXT_PUBLIC_*` prefix. API tokens, DSNs, passwords, provider keys and internal endpoints must never use that prefix.
