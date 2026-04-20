# Application Workflow

## Overview

This document describes the validated runtime workflow of the Actypity application as of `2026-04-20`.

## First-Run Authentication Workflow

### Preconditions

- `AUTH_ENABLED=true`
- `APP_STORAGE_BACKEND=postgres`
- PostgreSQL is reachable
- no API keys exist yet

### Flow

1. frontend loads `GET /health`
2. frontend loads `GET /auth/status`
3. backend reports `bootstrap_required=true`
4. frontend shows the bootstrap form
5. user submits `POST /auth/bootstrap` with:
   - `X-Bootstrap-Token`
   - `{ "name": "<admin key name>" }`
6. backend creates the first admin API key
7. frontend stores the returned raw API key locally
8. frontend reloads protected data with `X-API-Key`

### Result

The app becomes usable without any manual database edits.

## Standard Authenticated UI Workflow

1. frontend resolves the backend base URL in `frontend/src/api.ts`
2. frontend reads the stored API key from local storage
3. protected API calls automatically attach `X-API-Key`
4. on success, the UI loads:
   - agents
   - models
   - execution history
   - auth-aware status cards

If the API key is missing or invalid:

- protected endpoints return `401`
- the UI stays on the auth panel until a valid key is loaded

## Task Execution Workflow

### Request path

1. user submits a task from the frontend
2. frontend calls `POST /execute`
3. backend validates auth and RBAC
4. orchestrator resolves the target agent through internal scoring APIs
5. selected agent executes through an internal execution API
6. model-backed agents call the internal model completion API
7. execution is persisted
8. metrics are updated
9. logs are written
10. response is returned to the frontend

### Persisted records

- `executions`
- `agent_metrics`
- `execution_logs`

## Workflow Definition And Execution Flow

### Workflow definition

1. user or API client calls `POST /workflows/definitions`
2. backend stores:
   - workflow name
   - description
   - ordered steps
   - creator

### Workflow execution

1. client calls `POST /workflows/execute`
2. backend loads the workflow definition from PostgreSQL
3. backend creates a workflow execution record
4. workflow executor runs each step through the orchestrator
5. each step creates its own execution row and metrics/logs
6. backend updates the workflow execution record with results

### Persisted records

- `workflow_definitions`
- `workflow_executions`
- per-step `executions`
- `agent_metrics`
- `execution_logs`

## Agent Registry Workflow

1. container builds the agent registry in memory
2. startup sync writes registry metadata to PostgreSQL
3. `GET /agents` reads from PostgreSQL when available
4. if registry sync/read fails, the API can fall back to the in-memory registry listing

## Model Registry Workflow

1. container builds model profiles from environment-aware settings
2. `GET /models` exposes the catalog publicly
3. internal model execution uses `/internal/models/complete`
4. agents can prefer specific model profiles

## Logging Workflow

1. app startup configures logging through `backend/log_handler.py`
2. application and orchestration events emit standard log records
3. log handler persists records into PostgreSQL
4. `GET /logs` returns recent log entries
5. `execution_id` query filtering allows targeted investigation

## Metrics Workflow

1. orchestrator records execution outcomes by agent
2. metrics service writes aggregated counters to PostgreSQL
3. `GET /metrics` returns persisted metrics

Tracked values include:

- total executions
- LLM executions
- failed executions
- last execution time

## Environment Workflow

### Local PostgreSQL

Current validated local configuration:

```env
APP_STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg:///actypity?host=/tmp&user=kdn_aisivarajm
```

### Cloud PostgreSQL

Supported production pattern:

```env
APP_STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg://user:password@host:5432/database?sslmode=require
```

## Validation Workflow

The current recommended validation sequence is:

1. compile backend Python files
2. run frontend lint
3. run frontend production build
4. run backend unit and API tests
5. run PostgreSQL integration tests
6. run a live protected smoke workflow:
   - `/health`
   - `/auth/status`
   - `/auth/bootstrap`
   - `/models`
   - `/agents`
   - `/execute`
   - `/workflows/definitions`
   - `/workflows/execute`
   - `/metrics`
   - `/logs`
   - `/executions`
   - `/workflows/executions`

## Operational Notes

- the first bootstrap-created admin key is shown only once
- if LLM config is missing, execution still succeeds in deterministic fallback mode
- PostgreSQL is the system of record for auth, logs, metrics, registry, workflow definitions, and workflow runs
