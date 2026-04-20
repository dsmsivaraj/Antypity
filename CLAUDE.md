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
backend/          FastAPI app, container, config, LLM client, storage, schemas
agents/           Agent registry, orchestrator, skill definitions, agent implementations
shared/           BaseAgent ABC, Skill, AgentMetadata, AgentResult
frontend/src/     React app, typed API client, TypeScript types, CSS
k8s/              Kubernetes manifests
scripts/          Git wrapper utility
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

---

## Known gaps (do not need re-discovery)

| ID | Issue | File |
|---|---|---|
| G1 | `LLMClient.complete()` live API call not in try/except | `backend/llm_client.py:51` |
| G2 | `max_tokens=900` hardcoded | `backend/llm_client.py:53` |
| G3 | `.env` has stale Cosmos DB vars | `.env` |
| G4 | `azure-identity` in requirements but never used | `backend/requirements.txt` |
| G5 | `Dockerfile.backend` missing `PYTHONPATH` env var | `Dockerfile.backend` |
| G6 | No auth on any endpoint | `backend/main.py` |
| G7 | No test suite | entire project |
| G8 | `GeneralistAgent.can_handle()` always returns 40 regardless of task | `agents/example_agent.py:28` |
| G9 | K8s `secrets.yaml` has placeholder base64 values | `k8s/secrets.yaml` |

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
# Backend compile check
python -m py_compile backend/main.py agents/agent_orchestrator.py

# Backend import check
PYTHONPATH=. python -c "from backend.main import app; print('ok')"

# Frontend
cd frontend && npm run lint && npm run build

# Smoke test (backend running)
curl http://localhost:8000/health
curl -X POST http://localhost:8000/execute \
  -H 'Content-Type: application/json' \
  -d '{"task": "add 3 and 5"}'
```