# Antypity

Antypity contains the Actypity production-ready application base for building agent-enabled products with a FastAPI backend and a React frontend.

[![CI](https://github.com/dsmsivaraj/Antypity/actions/workflows/ci.yml/badge.svg)](https://github.com/dsmsivaraj/Antypity/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](./backend/requirements.txt)
[![React](https://img.shields.io/badge/React-18-61DAFB?logo=react&logoColor=111827)](./frontend/package.json)

## What is included

- FastAPI app factory with health, readiness, agent registry, execution, and history endpoints
- Deterministic agent routing with a pluggable LLM adapter
- Safe startup behavior when Azure OpenAI or PostgreSQL are not configured
- PostgreSQL-ready execution persistence with environment-driven local or cloud connectivity
- Typed React frontend with a Bootstrap-based control plane, model catalog, execution workspace, registry view, and history panel
- Docker and Kubernetes manifests aligned to the same runtime contract

## Repository assets

- [Contribution Guide](./CONTRIBUTING.md)
- [License](./LICENSE)
- [Application Knowledge](./APPLICATION_KNOWLEDGE.md)
- [Application Skills](./APPLICATION_SKILLS.md)
- [Application Workflow](./APPLICATION_WORKFLOW.md)
- [Validation Report](./VALIDATION_REPORT.md)

## Engineering references

- [Application Knowledge](./APPLICATION_KNOWLEDGE.md)
- [Application Skills](./APPLICATION_SKILLS.md)
- [Application Workflow](./APPLICATION_WORKFLOW.md)
- [Validation Report](./VALIDATION_REPORT.md)

## Screenshot

![Antypity UI](./docs/assets/antypity-hero.png)

## Quick start

### Local full stack

1. Configure `.env`
2. Start the backend:
   `./run_backend.sh`
3. Start the frontend:
   `cd frontend && npm install && npm run dev`
4. Open:
   `http://localhost:5173`

## Runtime contract

- Backend: `http://localhost:8000`
- Frontend dev: `http://localhost:5173`
- Frontend preview/container: `http://localhost:4173`

## Backend setup

1. Create the virtual environment if needed:
   `python3 -m venv backend/venv`
2. Start the backend:
   `./run_backend.sh`

The script activates the virtual environment, installs backend dependencies, sets `PYTHONPATH`, and runs:

`uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000`

### Backend environment variables

Required only for Azure OpenAI:

- `AZURE_OPENAI_API_KEY`
- `AZURE_OPENAI_ENDPOINT`
- `AZURE_OPENAI_DEPLOYMENT`

Optional platform settings:

- `APP_NAME`
- `APP_VERSION`
- `API_HOST`
- `API_PORT`
- `CORS_ORIGINS`
- `APP_STORAGE_BACKEND` (`postgres`, `json`, or `memory`) and defaults to `postgres`
- `APP_STORAGE_PATH`
- `DATABASE_URL` or `POSTGRES_DSN`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DATABASE`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_SSLMODE`
- `AUTH_ENABLED`
- `DEFAULT_ADMIN_KEY`
- `BOOTSTRAP_ADMIN_TOKEN`
- `SECRET_KEY`

### PostgreSQL configuration modes

Local PostgreSQL via explicit settings:

- `APP_STORAGE_BACKEND=postgres`
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `POSTGRES_DATABASE=actypity`
- `POSTGRES_USER=postgres`
- `POSTGRES_PASSWORD=postgres`

Cloud PostgreSQL via connection string:

- `APP_STORAGE_BACKEND=postgres`
- `DATABASE_URL=postgresql+psycopg://user:password@host:5432/database?sslmode=require`

Offline development fallback:

- `APP_STORAGE_BACKEND=json`

or:

- `APP_STORAGE_BACKEND=memory`

### Current validated local PostgreSQL setup

```env
APP_STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg:///actypity?host=/tmp&user=kdn_aisivarajm
```

## Frontend setup

1. Install dependencies:
   `cd frontend && npm install`
2. Start the Vite dev server:
   `npm run dev`

Optional:

- `VITE_API_BASE_URL` to point the UI at a non-default backend URL

## Docker

Build and run the full stack:

```bash
docker compose up --build
```

Services:

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:4173`

## Validation summary

The current baseline has been validated with:

- backend compile checks
- frontend lint
- frontend production build
- backend unit and API tests
- PostgreSQL integration tests
- a live authenticated workflow covering bootstrap, execution, workflows, metrics, logs, and history

See [VALIDATION_REPORT.md](./VALIDATION_REPORT.md) for the detailed report.

## API surface

- `GET /health`
- `GET /ready`
- `GET /auth/status`
- `POST /auth/bootstrap`
- `GET /models`
- `GET /agents`
- `GET /executions`
- `POST /execute`
- `GET /metrics`
- `GET /logs`
- `POST /workflows/definitions`
- `GET /workflows/definitions`
- `POST /workflows/execute`
- `GET /workflows/executions`

## Authentication bootstrap

When auth is enabled and no API keys exist yet:

1. call `GET /auth/status`
2. if `bootstrap_required=true`, call `POST /auth/bootstrap`
3. send `X-Bootstrap-Token` using `BOOTSTRAP_ADMIN_TOKEN` or `SECRET_KEY`
4. store the returned API key
5. use that value as `X-API-Key` for protected endpoints

The frontend already supports this bootstrap and API-key loading flow.

## Multi-agent and multi-model orchestration

The backend now supports:

- multi-agent routing through internal score and execution APIs
- multi-model selection through a public model catalog
- agent-specific preferred model profiles
- workflow execution that uses the same API-driven orchestration path as direct task execution

## Suggested next layers for product teams

- Add tenancy boundaries and identity federation
- Introduce background jobs for long-running workflows
- Add CI with lint, build, API smoke tests, and frontend integration tests
- Add observability, tracing, and deployment automation
