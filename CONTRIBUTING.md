# Contributing

## Development baseline

Antypity is maintained as a production-oriented full-stack base. Changes should preserve:

- typed backend and frontend contracts
- deterministic fallback behavior when Azure OpenAI is unavailable
- PostgreSQL-backed operational state
- authenticated and role-gated protected endpoints

## Local setup

1. Configure the backend environment in `.env`
2. Start PostgreSQL locally or point `DATABASE_URL` at a cloud instance
3. Start the backend:
   `./run_backend.sh`
4. Start the frontend:
   `cd frontend && npm install && npm run dev`

## Required validation before commit

### Backend

```bash
./backend/venv/bin/python -m py_compile backend/*.py agents/*.py shared/*.py tests/*.py
APP_STORAGE_BACKEND=json PYTHONPATH=$(pwd) ./backend/venv/bin/pytest tests/test_agents.py tests/test_orchestrator.py tests/test_workflow.py tests/test_api.py tests/test_auth.py tests/test_storage.py -q
DATABASE_URL='postgresql+psycopg:///actypity?host=/tmp&user=kdn_aisivarajm' APP_STORAGE_BACKEND=postgres PYTHONPATH=$(pwd) ./backend/venv/bin/pytest tests/test_postgres_integration.py -q
```

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

## Pull request expectations

- keep route handlers thin
- update backend schemas and frontend types together
- add or update tests for behavior changes
- do not commit local runtime artifacts, secrets, or database dumps
- document workflow or architectural changes in:
  - `APPLICATION_KNOWLEDGE.md`
  - `APPLICATION_WORKFLOW.md`
  - `VALIDATION_REPORT.md` when validation changes materially

## Commit guidance

Prefer focused commits with messages that describe the user-visible or platform-visible outcome.

Examples:

- `Add PostgreSQL-backed auth bootstrap flow`
- `Persist workflow metrics and logs in PostgreSQL`
- `Fix frontend protected-data reload after API key changes`
