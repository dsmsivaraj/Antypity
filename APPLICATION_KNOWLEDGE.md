# Application Knowledge

## Purpose

Actypity is a production-ready base for agent-enabled applications with:

- a FastAPI backend
- a React and TypeScript frontend
- a deterministic multi-agent orchestration layer with internal ASGI-based API routing
- optional Azure OpenAI augmentation with deterministic fallback
- PostgreSQL-backed persistence for executions, auth, logs, metrics, registry, and workflows

This document is the current architecture reference for maintaining and extending the codebase safely.

## Current Architecture

### Backend

Primary backend files:

- `backend/main.py`
  Owns the FastAPI app factory, lifecycle, and API routes.
- `backend/container.py`
  Builds the application container and wires settings, auth, logging, database, metrics, model router, internal API, registry, orchestrator, and workflow executor.
- `backend/config.py`
  Defines typed environment-driven settings for local and cloud deployments.
- `backend/database.py`
  Owns PostgreSQL connectivity, schema bootstrap, `reset_all()` for test isolation, and repository-style persistence methods.
- `backend/storage.py`
  Implements execution history backends (`InMemoryExecutionStore`, `JsonExecutionStore`, `PostgreSQLExecutionStore`) and selects the active store via `build_execution_store()`.
- `backend/auth.py`
  Implements API-key auth, RBAC, and first-admin bootstrap logic.
- `backend/log_handler.py`
  Persists application logs into PostgreSQL via `PostgreSQLLogHandler`. Filters `backend.database` and `sqlalchemy` loggers to prevent recursion.
- `backend/metrics.py`
  Records per-agent execution metrics into PostgreSQL via upsert.
- `backend/llm_client.py`
  Wraps Azure OpenAI with lazy initialization, try/except on API calls, and deterministic fallback output.
- `backend/model_router.py`
  Defines the model catalog (`ModelProfile`) and profile-aware completion routing. Builds profiles from settings (azure-general, azure-planner, azure-reviewer, fallback profiles). Used by `GET /models` and `POST /internal/models/complete`.
- `backend/internal_api.py`
  Provides the internal API client (`InternalPlatformAPI`) used by the orchestrator. Uses httpx with ASGI transport to call the FastAPI app in-process — no network round-trip. Protected by `X-Internal-Token`.
- `backend/schemas.py`
  Defines the API contracts consumed by the frontend and tests.

### Agent Layer

Primary agent files:

- `agents/agent_registry.py`
  Registers and resolves agents by name.
- `agents/agent_orchestrator.py`
  Routes tasks, executes agents via `InternalPlatformAPI`, persists execution history, and records metrics. `orchestrate()` is async.
- `agents/example_agent.py`
  Contains the current production baseline agents:
  - `GeneralistAgent` — score 40 catch-all; preferred model `azure-general`; uses `build_prompt()` → LLM
  - `PlannerAgent` — score 92 for plan/roadmap/steps keywords, 25 baseline; preferred model `azure-planner`
  - `ReviewerAgent` — score 88 for review/bug/risk/audit keywords, 20 baseline; preferred model `azure-reviewer`
  - `MathAgent` — score 90 for arithmetic keywords, 70 for 2+ numbers; deterministic, no LLM
- `agents/workflow_engine.py`
  Executes workflow definitions step by step through the orchestrator so workflow steps also create execution records, metrics, and logs. Supports `{previous_output}` template interpolation.
- `agents/agent_skills.py`
  Defines deterministic reusable skills (`summarize_context`, `add_numbers`).

### Shared Layer

- `shared/base_agent.py`
  Defines `BaseAgent`, `AgentMetadata`, `AgentResult`, and `Skill`. `AgentMetadata` has `preferred_model: Optional[str]`. `BaseAgent` has `build_prompt()` returning `Optional[Dict[str, str]]` — if non-None, the internal execute route uses the model router instead of calling `agent.execute()` directly.

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

### Protected endpoints (require `X-API-Key`)

- `GET /agents`
- `GET /models`
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

### Internal endpoints (require `X-Internal-Token`, not in OpenAPI schema)

- `POST /internal/agents/{name}/score`
- `POST /internal/agents/{name}/execute`
- `GET /internal/models`
- `POST /internal/models/complete`

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

- `admin` — unrestricted access
- `operator` — execute, workflow execute, logs read, metrics read, registry/history read
- `viewer` — read-only access to registry, history, logs, metrics, and workflow history

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

Persisted entities and their tables:

| Entity | Table | Key fields |
|---|---|---|
| Execution history | `executions` | execution_id, agent_name, status, output, used_llm, model_profile, provider, created_at, context |
| API keys | `api_keys` | id, name, key_hash (SHA-256), role, created_at, is_active |
| Agent registry | `agent_registry` | name, description, capabilities, supports_tools, agent_class, is_active |
| Execution logs | `execution_logs` | id, execution_id, level, logger, message, agent_name, timestamp |
| Agent metrics | `agent_metrics` | agent_name, total_executions, llm_executions, failed_executions, last_executed_at |
| Workflow definitions | `workflow_definitions` | id, name, description, steps (JSON), created_by, created_at |
| Workflow executions | `workflow_executions` | id, workflow_id, status, current_step, total_steps, results (JSON), error |

Schema is bootstrapped via SQLAlchemy `create_all()` on first connect. `reset_all()` drops and recreates all tables — for test isolation only.

## Environment Variables

### Platform

```env
APP_NAME=Actypity Backend
APP_VERSION=2.0.0
DEBUG=false
SECRET_KEY=change-me-in-production
BOOTSTRAP_ADMIN_TOKEN=
INTERNAL_API_TOKEN=
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
AZURE_OPENAI_PLANNER_DEPLOYMENT=
AZURE_OPENAI_REVIEWER_DEPLOYMENT=
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

Routing is deterministic and score-based. The orchestrator calls internal ASGI score APIs for all registered agents, picks the highest non-zero score, and executes via the internal execute API.

- explicit `agent_name` wins if present and registered
- otherwise all registered agents are scored via `/internal/agents/{name}/score`
- highest non-zero score wins
- `GeneralistAgent` (score 40) is the catch-all baseline

### Internal orchestration flow

1. `AgentOrchestrator.orchestrate()` calls `InternalPlatformAPI.score_agent()` for each agent
2. `InternalPlatformAPI` uses httpx ASGI transport to hit `/internal/agents/{name}/score`
3. Winning agent is called via `/internal/agents/{name}/execute`
4. Execute route checks `agent.build_prompt()` — if non-None, routes through `ModelRouter.complete()` using the agent's preferred model profile
5. If `build_prompt()` returns None, calls `agent.execute()` directly (e.g. MathAgent)

### Workflow execution

1. Load workflow definition from PostgreSQL
2. Build `WorkflowStep` objects with task templates
3. Create workflow execution row
4. Execute each step through the orchestrator (creates execution records, metrics, logs)
5. Pass `{previous_output}` from each step to the next via template rendering
6. Persist workflow execution results

### Multi-model behavior

Model profiles are built from settings:

- `azure-general` — default Azure deployment (when LLM configured)
- `azure-planner` — separate planner deployment (when `AZURE_OPENAI_PLANNER_DEPLOYMENT` set)
- `azure-reviewer` — separate reviewer deployment (when `AZURE_OPENAI_REVIEWER_DEPLOYMENT` set)
- `fallback-fast` / `fallback-critic` — deterministic fallback profiles (always present)

## Validation Status

Validation last updated: `2026-04-20`

Validated successfully:

- backend full compile check (all 18 modules)
- backend import check (`from backend.main import app`)
- frontend ESLint clean
- frontend production build (Vite)
- full pytest suite: 99 tests passing
  - unit tests: agents, orchestrator, storage, auth, API, workflow
  - PostgreSQL integration tests: executions, metrics, logs, registry, auth keys
- live authenticated workflow validated against local PostgreSQL-backed app

Live workflow validated:

- health and auth status
- first-admin bootstrap
- protected registry and model listing
- task execution (math, generalist, planner, reviewer routing)
- workflow definition creation and execution
- metrics read
- logs read and execution-specific filtering
- execution history read with model_profile and provider fields

## Known Gaps

| ID | Issue | Status |
|---|---|---|
| G2 | `MAX_TOKENS` default 2000 may be too high for some deployments | Open — configure via env |
| G3 | `.env` has stale Cosmos DB vars | Open — ignore, overridden by real vars |
| G4 | `azure-identity` in requirements but never imported | Open — remove when cleaned up |
| G8 | `GeneralistAgent.can_handle()` always returns 40 | Open by design — it's the catch-all |
| G9 | K8s `secrets.yaml` has placeholder base64 values | Open — fill before production deploy |
| G10 | No formal migration framework; `reset_all()` drops/recreates for tests only | Open — add Alembic for production migrations |
| G11 | No user-facing API key management UI beyond bootstrap and manual key loading | Open |
| G12 | No background queue for long-running workflow execution | Open |
| G13 | No OpenTelemetry tracing or structured request correlation | Open |

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
3. optionally implement `build_prompt()` to use the model router
4. return `AgentResult`
5. register it in `backend/container.py`
6. ensure registry sync still writes it to PostgreSQL
7. add or update tests

### Change PostgreSQL-backed persistence

1. update `backend/database.py` (table definition + methods)
2. update `backend/storage.py` only if execution-store behavior changes
3. update route responses if persisted data shape changes
4. add or update PostgreSQL integration tests
5. note: `create_all()` does not ALTER existing tables — use `reset_all()` in tests; plan a migration for production

### Change auth behavior

1. update `backend/auth.py`
2. keep `/health` and `/auth/status` aligned
3. keep frontend bootstrap and API-key loading flows aligned
4. update tests for bootstrap and RBAC expectations
