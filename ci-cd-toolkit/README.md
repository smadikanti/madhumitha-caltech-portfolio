# ci-cd-toolkit

Reusable CI/CD framework for Python apps. GitHub Actions workflows, multi-stage Dockerfile, Kubernetes manifests, and deployment scripts.

## Local dev

```bash
make setup    # install deps + pre-commit hooks
make run      # docker-compose up (app + postgres + redis + prometheus)
make test     # pytest
make lint     # ruff
make stop     # tear down
```

Run `make help` for all targets.

## What's in here

- `.github/workflows/` — CI (lint→test→build→scan), deploy (env promotion with approvals), release (semver tag → changelog → GitHub Release)
- `Dockerfile` — multi-stage build, non-root user, health check
- `docker-compose.yml` — local stack: app + PostgreSQL + Redis + Prometheus
- `k8s/` — Deployment, Service, ConfigMap, HPA, Ingress (with TLS)
- `scripts/` — `deploy.sh` (rolling/blue-green), `rollback.sh`, `health-check.sh`, `version.sh`
- `envs/` — per-environment `.env` files
- `Makefile` — dev task runner
- `app/` — sample Flask app with `/health` and `/ready` endpoints

## Deploy

```bash
make deploy ENV=staging
make deploy ENV=prod
make rollback ENV=prod
make version BUMP=patch
```

Promotion path: dev → staging → prod. Production requires GitHub environment approval.
