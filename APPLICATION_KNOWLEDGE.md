# Application Knowledge

## Purpose

Actypity is a production-ready base for agent-enabled applications with:

- a FastAPI backend
- a React and TypeScript frontend
- a deterministic multi-agent orchestration layer
- optional Azure OpenAI augmentation with deterministic fallback
- PostgreSQL-backed persistence for executions, auth, logs, metrics, registry, and workflows

This document is the current architecture reference for maintaining and extending the codebase safely.

## Current Architecture

### Backend

Primary backend files:

- `backend/main.py`
  Owns the FastAPI app factory, lifecycle, and API routes.
- `backend/container.py`
  Builds the application container and wires settings, auth, logging, database, metrics, registry, orchestrator, and workflow executor.
- `backend/config.py`
  Defines typed environment-driven settings for local and cloud deployments.
- `backend/database.py`
  Owns PostgreSQL connectivity, schema bootstrap, and repository-style persistence methods.
- `backend/storage.py`
  Implements execution history backends and selects the active store.
- `backend/auth.py`
  Implements API-key auth, RBAC, and first-admin bootstrap logic.
- `backend/log_handler.py`
  Persists application logs into PostgreSQL.
- `backend/metrics.py`
  Records per-agent execution metrics into PostgreSQL.
- `backend/llm_client.py`
  Wraps Azure OpenAI with lazy initialization and deterministic fallback output.
- `backend/model_router.py`
  Defines the model catalog and profile-aware completion routing for multi-model execution.
- `backend/internal_api.py`
  Provides the internal HTTP client used by the orchestrator to call agent and model APIs.
- `backend/schemas.py`
  Defines the API contracts consumed by the frontend and tests.

### Agent Layer

Primary agent files:

- `agents/agent_registry.py`
  Registers and resolves agents.
- `agents/agent_orchestrator.py`
  Routes tasks, executes agents, persists execution history, and records metrics.
- `agents/example_agent.py`
  Contains the current production baseline agents:
  - `GeneralistAgent`
  - `PlannerAgent`
  - `ReviewerAgent`
  - `MathAgent`
- `agents/workflow_engine.py`
  Executes workflow definitions step by step through the orchestrator so workflow steps also create execution records, metrics, and logs.
- `agents/agent_skills.py`
  Defines deterministic reusable skills.

### Shared Layer

- `shared/base_agent.py`
  Defines `BaseAgent`, `AgentMetadata`, `AgentResult`, and `Skill`.

### Frontend

Primary frontend files:

- `frontend/src/App.tsx`
  Bootstrap-based control plane for health, auth bootstrap, model selection, task execution, and history loading.
- `frontend/src/api.ts`
  Typed API client and localStorage-backed API key handling.
- `frontend/src/types.ts`
  Frontend mirror of backend response models.
- `frontend/src/App.css`
  Application layout and component styling.

## Current API Surface

### Public endpoints

- `GET /`
- `GET /health`
- `GET /ready`
- `GET /auth/status`
- `POST /auth/bootstrap`
- `GET /models`

### Protected endpoints

All protected endpoints require `X-API-Key`.

- `GET /agents`
- `GET /executions`
- `POST /execute`
- `POST /auth/keys`
- `GET /auth/keys`
- `DELETE /auth/keys/{key_id}`
- `GET /metrics`
- `GET /logs`
- `POST /workflows/definitions`
- `GET /workflows/definitions`
- `POST /workflows/execute`
- `GET /workflows/executions`

## Authentication And RBAC

Auth is API-key based and backed by PostgreSQL.

### First-run bootstrap

When no API keys exist:

- `GET /health` returns `auth_bootstrap_required=true`
- `GET /auth/status` returns `bootstrap_required=true`
- protected endpoints return `401` with bootstrap guidance
- `POST /auth/bootstrap` becomes the only path to create the first admin key

Bootstrap request requirements:

- header: `X-Bootstrap-Token`
- body: `{ "name": "<admin key name>" }`

Bootstrap token source:

- `BOOTSTRAP_ADMIN_TOKEN`
- falls back to `SECRET_KEY` if not explicitly set

### Roles

- `admin`
  Unrestricted access
- `operator`
  Execution, workflow execution, logs read, metrics read, and registry/history read
- `viewer`
  Read-only access to registry, history, logs, metrics, and workflow history

## Runtime Contract

| Context | URL |
|---|---|
| Backend local | `http://localhost:8000` |
| Frontend dev | `http://localhost:5173` |
| Frontend preview/container | `http://localhost:4173` |

When ports change, update:

- backend CORS origins
- frontend `VITE_API_BASE_URL`
- Docker Compose mappings
- deployment manifests

## PostgreSQL Persistence Map

The platform now stores operational state in PostgreSQL instead of local-only files.

Persisted entities:

- execution history
- API keys
- agent registry records
- execution logs
- agent metrics
- workflow definitions
- workflow executions

The database client supports:

- local PostgreSQL via explicit host/port settings
- cloud PostgreSQL via `DATABASE_URL` or `POSTGRES_DSN`
- automatic table bootstrap on connect

## Environment Variables

### Platform

```env
APP_NAME=Actypity Backend
APP_VERSION=2.0.0
DEBUG=false
SECRET_KEY=change-me-in-production
BOOTSTRAP_ADMIN_TOKEN=
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:5173,http://localhost:4173
REQUEST_TIMEOUT_SECONDS=30
MAX_TOKENS=2000
```

### Storage

```env
APP_STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database
POSTGRES_DSN=
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=actypity
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_SSLMODE=
```

### Azure OpenAI

```env
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_API_VERSION=2024-02-01
```

## Frontend Runtime Behavior

The frontend boot sequence is:

1. load `/health`
2. load `/auth/status`
3. if auth is disabled, or an API key is already present, load protected data
4. if bootstrap is required, show the bootstrap form
5. if an API key is pasted manually, save it and reload protected data

The API client is the only owner of:

- backend base URL resolution
- `X-API-Key` header injection
- API key local storage helpers

## Routing And Workflow Behavior

### Routing

Routing is deterministic and score-based, but orchestration now happens through internal APIs instead of direct agent function calls.

- explicit `agent_name` wins if present
- otherwise the orchestrator calls internal score APIs for all registered agents
- highest non-zero score wins
- `GeneralistAgent` is the fallback baseline

### Internal orchestration APIs

The backend now uses internal HTTP APIs for orchestration:

1. `/internal/agents/{name}/score`
2. `/internal/agents/{name}/execute`
3. `/internal/models`
4. `/internal/models/complete`

This keeps orchestration API-shaped and makes later externalization easier.

### Workflow execution

Workflow definitions are persisted.

Workflow execution path:

1. load workflow definition from PostgreSQL
2. build `WorkflowStep` objects
3. create workflow execution row
4. execute each step through the orchestrator
5. persist workflow execution results

This is important because workflow steps now create:

- normal execution rows
- agent metrics
- execution logs

### Multi-model behavior

The backend exposes a public model catalog and supports agent-level preferred model profiles.

Current model profile families:

- general Azure profile
- planner Azure profile when configured
- reviewer Azure profile when configured
- deterministic fallback profiles

## Validation Status

Validation last updated: `2026-04-20`

Validated successfully:

- backend compile checks
- frontend lint
- frontend production build
- backend unit and API test suite
- PostgreSQL integration tests against the local `actypity` database
- live authenticated workflow against the local PostgreSQL-backed app

Live workflow validated:

- health and auth status
- first-admin bootstrap
- protected registry access
- task execution
- workflow definition creation
- workflow execution
- metrics read
- logs read and execution-specific filtering
- execution history read

## Known Gaps

Current production gaps worth addressing next:

- no formal migration framework; schema changes currently rely on table bootstrap behavior
- no user-facing API key management UI beyond first bootstrap and manual key loading
- no background queue for long-running workflow execution
- no OpenTelemetry tracing or structured request correlation yet
- Azure OpenAI is currently optional and can remain in deterministic fallback mode if env vars are placeholders

## Change Zone Guide

### Add a new protected API endpoint

1. define the schema in `backend/schemas.py`
2. add the route in `backend/main.py`
3. gate it with `_require("<permission>")`
4. update `frontend/src/types.ts`
5. add the client function in `frontend/src/api.ts`
6. wire the UI in `frontend/src/App.tsx` or a new component

### Add a new agent

1. implement the agent in `agents/`
2. give `can_handle()` a meaningful score
3. return `AgentResult`
4. register it in `backend/container.py`
5. ensure registry sync still writes it to PostgreSQL
6. add or update tests

### Change PostgreSQL-backed persistence

1. update `backend/database.py`
2. update `backend/storage.py` only if execution-store behavior changes
3. update route responses if persisted data shape changes
4. add or update PostgreSQL integration tests

### Change auth behavior

1. update `backend/auth.py`
2. keep `/health` and `/auth/status` aligned
3. keep frontend bootstrap and API-key loading flows aligned
4. update tests for bootstrap and RBAC expectations
