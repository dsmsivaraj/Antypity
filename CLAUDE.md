# Actypity — Claude Code Project Guide

## What this project is

Actypity is an AI agent orchestration platform. It consists of:

- **Backend**: FastAPI + Python, score-based agent routing, PostgreSQL/JSON/memory execution persistence, Azure OpenAI integration with deterministic fallback
- **Frontend**: React 19 + TypeScript, Vite, typed API client
- **Infra**: Docker Compose, Kubernetes manifests, Azure deployment target

Full architecture detail: `APPLICATION_KNOWLEDGE.md`
Engineering skills and playbooks: `APPLICATION_SKILLS.md`

---

## Repository layout

```
backend/          FastAPI app, container, config, LLM client, model router, internal API, storage, schemas
agents/           Agent registry, orchestrator, skill definitions, agent implementations
shared/           BaseAgent ABC, Skill, AgentMetadata, AgentResult
frontend/src/     React app, typed API client, TypeScript types, CSS
k8s/              Kubernetes manifests
tests/            pytest suite (99 tests, unit + PostgreSQL integration)
```

---

## How to run locally

```bash
# Backend (from project root)
source activate_and_update_venv.sh
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# Or use the script (starts on port 8002 — see port note below)
./run_backend.sh

# Frontend
cd frontend && npm install && npm run dev
```

**Port contract:** backend runs on `8000`, frontend Vite dev on `5173`, preview on `4173`.
`run_backend.sh` currently starts on `8002` — this conflicts with the frontend's expected `8000`. Use uvicorn directly or set `API_PORT=8002` and `VITE_API_BASE_URL=http://localhost:8002`.

**Storage for local dev:** set `APP_STORAGE_BACKEND=json` in `.env` to avoid needing PostgreSQL.

---

## Environment setup

Copy `.env` and fill in values. Minimum for local dev without Azure:

```bash
APP_STORAGE_BACKEND=json
DEBUG=true
SECRET_KEY=local-dev-key
```

The current `.env` has stale Cosmos DB vars — ignore them. See `APPLICATION_KNOWLEDGE.md` for the full env var reference.

---

## Key architectural rules

1. **Route handlers stay thin** — all logic is in the orchestrator, store, or LLM client
2. **Score-based routing** — `can_handle()` returns an int; highest wins; `GeneralistAgent` (score 40) is the catch-all and must always be registered
3. **LLM is optional** — `LLMClient.complete()` always returns an `LLMResult`; callers must handle `used_llm=False`
4. **Storage is swappable** — `APP_STORAGE_BACKEND`: `memory` | `json` | `postgres`
5. **Typed contracts** — any API schema change requires updating both `backend/schemas.py` and `frontend/src/types.ts`
6. **Internal orchestration via ASGI** — the orchestrator calls agents through `InternalPlatformAPI` using httpx ASGI transport, not direct function calls

---

## Known gaps

| ID | Issue | File | Status |
|---|---|---|---|
| G1 | `LLMClient.complete()` live API call not in try/except | `backend/llm_client.py` | **FIXED** |
| G2 | `max_tokens` driven by `MAX_TOKENS` env var (default 2000) | `backend/config.py` | Open — adjust via env |
| G3 | `.env` has stale Cosmos DB vars | `.env` | Open — ignore stale vars |
| G4 | `azure-identity` in requirements but never used | `backend/requirements.txt` | Open |
| G5 | `Dockerfile.backend` missing `PYTHONPATH` env var | `Dockerfile.backend` | **FIXED** |
| G6 | No auth on any endpoint | `backend/main.py` | **FIXED** — RBAC via X-API-Key |
| G7 | No test suite | entire project | **FIXED** — 99 tests |
| G8 | `GeneralistAgent.can_handle()` always returns 40 | `agents/example_agent.py` | Open by design (catch-all) |
| G9 | K8s `secrets.yaml` has placeholder base64 values | `k8s/secrets.yaml` | Open — fill before deploy |
| G10 | No formal migration framework; schema changes use `reset_all()` in tests | `backend/database.py` | Open |

---

## Adding a new agent (quick reference)

```python
# 1. Create in agents/
class MyAgent(BaseAgent):
    def can_handle(self, task, context=None) -> int:
        return 80 if "keyword" in task.lower() else 0

    def execute(self, task, context=None) -> AgentResult:
        return AgentResult(output="...", used_llm=False, metadata={})

# 2. Register in backend/container.py
registry.register(MyAgent())
```

---

## Validation commands

```bash
# Full compile check
PYTHONPATH=. python -m py_compile backend/main.py backend/container.py backend/config.py \
  backend/database.py backend/auth.py backend/log_handler.py backend/metrics.py \
  backend/model_router.py backend/internal_api.py backend/storage.py backend/schemas.py \
  agents/agent_orchestrator.py agents/agent_registry.py agents/example_agent.py \
  agents/agent_skills.py agents/workflow_engine.py shared/base_agent.py

# Backend import check
PYTHONPATH=. python -c "from backend.main import app; print('ok')"

# Full test suite
PYTHONPATH=. pytest tests/ -q

# Frontend
cd frontend && npm run lint && npm run build

# Smoke test (backend running, auth disabled or X-API-Key provided)
curl http://localhost:8000/health
curl -X POST http://localhost:8000/execute \
  -H 'Content-Type: application/json' \
  -d '{"task": "add 3 and 5"}'
```
