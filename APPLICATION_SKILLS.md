# Application Skills

## Role

Operate as a senior full-stack engineer specializing in GenAI backend design and React frontend engineering on the Actypity platform.

Engineering standard:
- Fix root causes, not surface symptoms
- Preserve architecture clarity and typed contracts
- Keep runtime behavior explicit and testable
- Avoid coupling layers that own separate responsibilities
- Make changes that work locally and in Docker identically

---

## Core Skill Areas

### 1. FastAPI backend engineering

- Keep route handlers in `main.py` thin — delegate all logic to the container, orchestrator, or store
- Change API shapes in `backend/schemas.py` first, then update handlers and frontend types together
- Use the `AppContainer` from `app.state.container` — never re-instantiate services inside handlers
- Preserve lifespan context: `container` must be attached to `app.state` before request handlers run
- CORS must be driven by `Settings.cors_origins` — never hardcode origins in middleware registration
- Keep public and protected endpoints explicit; auth status and bootstrap flows are part of the contract

### 2. Agent system engineering

- New agents must inherit `BaseAgent` from `shared/base_agent.py`
- `can_handle()` must return an integer score; higher wins; 0 means "cannot handle"
- `GeneralistAgent` (score 40) is the catch-all — must stay registered or general tasks return 400
- `MathAgent` (score 70–90) is the specialist — scores high on numeric patterns, 0 otherwise
- `PlannerAgent` and `ReviewerAgent` are part of the default platform baseline and are used by workflows
- Register agents only in `backend/container.py` — never in route handlers or other agents
- Skills are pure functions wrapped in `Skill(name, description, handler)` — keep them stateless
- Registry changes must remain PostgreSQL-syncable through `backend/container.py`
- Implement `build_prompt()` returning `Dict[str, str]` if the agent uses the LLM via the model router; return `None` to use `execute()` directly (for deterministic agents like MathAgent)
- Set `preferred_model` in `AgentMetadata` to tie the agent to a specific model profile

### 3. Frontend engineering

- All HTTP calls go through `frontend/src/api.ts` — never inline fetch in components
- All backend response shapes are typed in `frontend/src/types.ts` — update before using new fields
- `App.tsx` owns UI state and orchestrates: `agents`, `health`, `history`, `authStatus`, `apiKey`, `bootstrapResult`, `activeExecution`, `loading`, `bootError`, `submitError`
- Every async flow must handle all four states: loading, success, error, empty
- Never hardcode backend URL outside `api.ts` — use `VITE_API_BASE_URL` env var or the fallback
- CSS is in `App.css` (page-level) and `index.css` (global primitives) — do not add inline styles
- Frontend auth flows must support:
  - first admin bootstrap
  - manual API key load
  - protected data reload after auth state changes

### 4. GenAI backend design

- The LLM is optional — `LLMClient.enabled` is false when env vars are missing
- `LLMClient.complete()` always returns an `LLMResult`; callers check `used_llm` not the content format
- Routing is score-based (deterministic), not LLM-based — keep it that way
- Prompt construction belongs in agents, not in `llm_client.py`
- LLM calls must be wrapped in try/except — Azure OpenAI can fail post-init (rate limits, network)
- `used_llm=False` in a result is valid and expected — do not treat it as an error

### 5. Persistence engineering

- Storage selection is via `APP_STORAGE_BACKEND` env var: `memory`, `json`, `postgres`
- `build_execution_store()` in `storage.py` is the single selection point — do not replicate this logic
- All store interactions go through `container.store` — route handlers never touch storage directly
- PostgreSQL is the production-grade default; JSON and memory are for local dev and testing
- Schema migrations are implicit (SQLAlchemy `create_all`) — add columns carefully to avoid data loss
- Logs, metrics, API keys, registry records, workflow definitions, and workflow executions must remain PostgreSQL-backed
- Do not move operational state back into local files unless the feature is explicitly a local-only fallback

### 6. Authentication and authorization engineering

- API-key auth is the current production baseline
- Protected routes must use `_require("<permission>")`
- Keep `/health` and `/auth/status` aligned with real auth state
- First-run usability depends on `/auth/bootstrap`; do not break that path
- `BOOTSTRAP_ADMIN_TOKEN` should be preferred over reusing `SECRET_KEY` in production deployments
- RBAC expectations must be covered by tests whenever permissions change

### 7. Workflow engineering

- Workflow definitions are persisted and executed through the orchestrator
- Workflow steps must not bypass the orchestrator, or metrics/logs/history will drift from reality
- If workflow result schemas change, update both:
  - backend workflow response models
  - frontend types and rendering paths

### 8. Bug fixing discipline

- Read the failing layer first: identify whether the bug is in routing, schema, storage, LLM, or frontend
- Verify with compile check, lint, or smoke test after every fix — not just visual inspection
- Do not widen the fix: a bug in `storage.py` does not justify refactoring `main.py`
- Check both local and Docker behavior for environment-related bugs

---

## Bug-Fix Playbooks

### Pattern: endpoint returns unexpected shape

Likely files:
- `backend/schemas.py` — schema fields mismatched
- `backend/main.py` — response model wrong or handler building wrong dict
- `frontend/src/types.ts` — type out of sync with actual response
- `frontend/src/api.ts` — parsing or casting issue

Fix order: schema → handler → frontend type → api.ts

---

### Pattern: agent execution returns 400 or wrong agent selected

Likely files:
- `agents/agent_orchestrator.py` — scoring logic or resolution error
- `agents/agent_registry.py` — agent not registered or name mismatch
- `agents/example_agent.py` — `can_handle()` returns wrong score
- `backend/container.py` — agent not wired into registry

Fix order: check registry wiring → check `can_handle()` scores → check `_resolve_agent()` logic

---

### Pattern: LLM call fails at runtime

Likely files:
- `backend/llm_client.py` — `_get_client()` lazy init or `complete()` network/rate-limit error
- `backend/config.py` — env vars not set or loaded from wrong `.env` path

`LLMClient.complete()` wraps the Azure API call in try/except and returns a fallback `LLMResult` on any exception. If LLM calls are silently falling back when you expect live results, check: `health.llm_enabled`, the Azure env vars, and `LLMClient.client_error`.

---

### Pattern: storage error (PostgreSQL)

Likely files:
- `backend/database.py` — connection string, schema creation, or query error
- `backend/config.py` — `resolved_postgres_dsn` not correct
- `backend/storage.py` — `PostgreSQLExecutionStore` not selected

Check: `APP_STORAGE_BACKEND=postgres`, `DATABASE_URL` or `POSTGRES_*` vars set, DB is reachable via `GET /ready`

---

### Pattern: protected endpoint returns 401 on first run

Check:
1. `GET /auth/status` — if `bootstrap_required=true`, this is expected
2. Call `POST /auth/bootstrap` with `X-Bootstrap-Token`
3. Save the returned API key
4. Retry the protected endpoint with `X-API-Key`

If bootstrap is unexpectedly false while no keys should exist:
- inspect the `api_keys` table in PostgreSQL
- verify the app can actually reach the configured database

---

### Pattern: workflow execution succeeds but logs/metrics are missing

Likely files:
- `agents/workflow_engine.py` — step execution bypassing orchestrator
- `agents/agent_orchestrator.py` — not persisting correctly
- `backend/metrics.py` — metrics write issue
- `backend/log_handler.py` — log persistence issue
- `backend/database.py` — query or transaction failure

Fix order:
- confirm workflow steps call the orchestrator
- confirm execution rows are created
- confirm metrics and logs tables are receiving writes

---

### Pattern: startup / import error

Likely files:
- `backend/container.py` — wiring error caught at build time
- `run_backend.sh` — `PYTHONPATH` not set to project root
- `Dockerfile.backend` — `PYTHONPATH` env var missing
- `backend/requirements.txt` — missing or pinned too low

Fix: run `PYTHONPATH=$(pwd) python -c "from backend.main import app"` to surface import errors

---

### Pattern: frontend build fails

Likely files:
- `frontend/src/types.ts` — type updated but consuming code not updated
- `frontend/src/App.tsx` — unused import (`noUnusedLocals` is on), bad JSX
- `frontend/src/api.ts` — function signature changed without updating call sites

Fix order: `npm run lint` → `npm run build` — address errors in the order the compiler reports

---

### Pattern: frontend shows "Backend connection failed"

Check:
1. Backend is running on port 8000 (`curl http://localhost:8000/health`)
2. `VITE_API_BASE_URL` is not set to a wrong port
3. CORS: `CORS_ORIGINS` includes `http://localhost:5173`
4. `npm run dev` is using port 5173 (Vite default)

---

## Required Engineering Behaviors

### Keep typed boundaries

If the backend API shape changes:
1. Update `backend/schemas.py`
2. Update `frontend/src/types.ts`
3. Update `frontend/src/api.ts` if the method signature or path changes
4. Never update only one side

### Preserve safe fallback

If LLM is not configured or fails:
- `LLMClient.complete()` must return an `LLMResult` with `used_llm=False`
- `AgentResult.output` must still be a useful string
- The API must return 200, not 500

If PostgreSQL is not reachable:
- Set `APP_STORAGE_BACKEND=json` or `memory` for local dev
- Never change the default without updating the `.env` or docs

### Avoid tight coupling

- Route handlers must not call the LLM directly — route handlers call the orchestrator
- Orchestrator must not call the store directly from agents — orchestrator saves after `agent.execute()`
- Agents must not instantiate their own LLM client — receive it via constructor injection

### Design for replacement

- New persistence layers implement `ExecutionStore` and register in `build_execution_store()`
- New agents implement `BaseAgent` and register in `container.py`
- New API clients are added to `api.ts` and typed in `types.ts`

---

## Validation After Changes

### Backend changes

```bash
# Compile check
python -m py_compile backend/*.py agents/*.py shared/*.py tests/*.py

# Import check (requires PYTHONPATH at project root)
PYTHONPATH=. python -c "from backend.main import app; print('ok')"

# Smoke tests (backend running, use X-API-Key when auth is enabled)
curl -s http://localhost:8000/health | python -m json.tool
curl -s http://localhost:8000/auth/status | python -m json.tool
curl -s http://localhost:8000/agents -H 'X-API-Key: <key>' | python -m json.tool
curl -s -X POST http://localhost:8000/execute \
  -H 'X-API-Key: <key>' \
  -H 'Content-Type: application/json' \
  -d '{"task": "add 10 and 20"}' | python -m json.tool
```

### Frontend changes

```bash
cd frontend
npm run lint
npm run build
```

### Integration check

After both are running:
- Open `http://localhost:5173`
- Confirm auth status is accurate
- If bootstrap is required, create the first admin key
- Load protected data with the API key
- Submit a task and confirm the result and history update
- Confirm logs and metrics are queryable from the backend

---

## What Good Changes Look Like

- One clear owner per responsibility
- No business logic in route handlers
- No fetch calls outside `api.ts`
- No hardcoded URLs, ports, or secrets in source code
- Frontend compiles cleanly after every backend schema change
- New agents are wired only in `container.py`
- Fallback behavior is preserved after any LLM-related change
- Operational data lands in PostgreSQL when `APP_STORAGE_BACKEND=postgres`

## What to Avoid

- Adding logic to `main.py` that belongs in `orchestrator`, `storage`, or `llm_client`
- Scattering backend URLs in frontend components
- Removing the `GeneralistAgent` catch-all without ensuring another catch-all exists
- Making PostgreSQL a hard startup dependency (breaks local dev without a DB)
- Changing ports in only one place
- Catching all exceptions silently without logging or returning a meaningful fallback
- Adding new protected endpoints without updating the frontend auth/bootstrap path when needed

---

## Future Skill Expansion

As the platform grows, add specialized skills for:

- **Authentication**: API key header middleware, Azure AD token validation
- **Streaming**: SSE endpoint for progressive LLM token delivery
- **Observability**: Structured JSON logging with `logging`, OpenTelemetry tracing
- **Testing**: pytest fixtures for the container, vitest for the API client
- **CI**: GitHub Actions workflows for lint, compile, build, smoke test
- **Prompt engineering**: Prompt templates, evaluation harnesses, model comparison
- **Multi-tenancy**: User context in `TaskRequest`, tenant-scoped execution history
