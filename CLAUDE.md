# Antypity — Claude Code Project Guide

## What this project is

Antypity (code-named *Actypity*) is a career-focused AI agent orchestration platform. It helps users with resume analysis, job search, cover letter generation, and career coaching through a multi-agent backend connected to a React frontend.

- **Backend**: FastAPI + Python 3.11, score-based agent routing, multi-provider LLM routing (Azure OpenAI / Google Gemini / Ollama / LLaMA-cpp / deterministic fallback), PostgreSQL + pgvector + FAISS embeddings, RBAC auth via `X-API-Key`, versioned prompt registry
- **Frontend**: React 19 + TypeScript, Vite, typed API client (`api.ts` ↔ `types.ts`)
- **Infra**: Docker Compose, Kubernetes manifests, Azure deployment target
- **Services**: Microservice stubs in `services/` (not yet active — future extraction targets)

Full architecture detail: `APPLICATION_KNOWLEDGE.md`
Engineering skills and playbooks: `APPLICATION_SKILLS.md`

---

## Repository layout

```
backend/               FastAPI app and all backend modules (see detail below)
  auth.py              RBAC: API key validation, roles (admin/operator/viewer)
  career_service.py    Job search, cover letter, resume templates, RAG pipeline
  config.py            Settings dataclass (from_env / for_testing)
  container.py         AppContainer: builds and wires all services + agents
  database.py          PostgreSQLDatabaseClient (SQLAlchemy 2, psycopg3)
  diagnostics.py       DiagnosticsService: health/test/code/reporter agents
  embeddings.py        VectorIndex + text_to_vector (token-overlap fallback)
  embeddings_service.py EmbeddingService (sentence-transformers + FAISS + pgvector)
  figma_client.py      Figma REST client
  gemini_client.py     Google Gemini AI client
  internal_api.py      InternalPlatformAPI (ASGI transport for in-process agent calls)
  job_search_service.py Job portal search (LinkedIn, Indeed, Glassdoor, etc.)
  jwt_utils.py         JWT creation/decode (python-jose, HS256, 7-day expiry)
  llama_client.py      llama-cpp-python client
  llm_adapter.py       normalize_completion: unifies LLMResult from all providers
  llm_client.py        Azure OpenAI client → LLMResult
  local_llm.py         OllamaClient (httpx, streaming-capable)
  log_handler.py       Structured logging → DB
  main.py              FastAPI app, all HTTP routes
  metrics.py           MetricsService + DBMetricsMixin
  model_router.py      ModelRouter: provider selection + fallback chain
  prompt_registry.py   Versioned prompt store (backend/data/prompts/<name>/<ver>.json)
  ratelimit.py         Request rate limiting
  remote_vector_client.py  RemoteEmbeddingService (optional external vector DB)
  requirements.txt     Python dependencies
  resume_parser.py     PDF/DOCX/text resume extraction + spaCy NER
  retrieval.py         RAG retrieval helpers
  scheduler.py         DiagnosticsScheduler (asyncio periodic task)
  schemas.py           Pydantic v2 request/response models (single source of truth)
  self_healing.py      InProcessSelfHealingController (runs alongside the app)
  storage.py           ExecutionStore ABC + JSON / memory / Postgres backends
  vector_service.py    Higher-level vector DB service
  migrations/          Raw SQL migration files (no framework — apply manually)
  data/prompts/        Versioned prompt JSON files (auto-created by registry)

agents/
  agent_orchestrator.py  AgentOrchestrator: routes tasks, stores results, emits metrics
  agent_registry.py      AgentRegistry: register/select by can_handle() score
  agent_skills.py        common_skills list (Skill dataclasses)
  chatbot_agent.py       ChatbotAgent + ChatStore (career Q&A)
  diagnostics_agent.py   HealthCheckAgent, TestRunnerAgent, CodeAnalyzerAgent, DiagnosticsReporterAgent
  example_agent.py       GeneralistAgent (catch-all, score 40), MathAgent, PlannerAgent, ReviewerAgent
  job_applicant_agent.py JobApplicantAgent (resume ↔ JD matching)
  job_search_agent.py    EnhancedJobSearchAgent
  resume_agent.py        LocalResumeAgent, LocalJDAgent, ResumeTemplateAgent (Ollama-powered)
  resume_skills_agent.py ResumeEvaluatorAgent, ResumeWriterAgent, ResumeReviewerAgent
  workflow_engine.py     WorkflowExecutor + WorkflowStep / StepResult / WorkflowResult

shared/
  base_agent.py          BaseAgent ABC, AgentMetadata, AgentResult, Skill

services/              Microservice stubs (future extraction — NOT wired into main app or tests)
  admin/orchestrator/identity/inference/chatbot/diagnostics/repair/
  resume_processor/job_scraper/ats_matcher/outreach/templates/tracker/

frontend/src/
  App.tsx              Main shell, overview + resume + execute panels
  AuthContext.tsx      React context for JWT + user state
  ChatPage.tsx         Career chatbot UI
  JobHuntPage.tsx      AI-powered job hunt with resume upload
  JobsPage.tsx         Job search + JD extractor
  LoginPage.tsx        API key + Google OAuth login
  ProfilePage.tsx      User profile + session management
  PromptAdmin.tsx      Admin prompt version viewer
  TemplatesPage.tsx    Resume template designer (Figma-backed)
  api.ts               Typed API client (all fetch calls)
  types.ts             TypeScript types mirroring backend/schemas.py

k8s/                   Kubernetes manifests (backend + frontend deployments, secrets)
tests/                 pytest suite (16 test files; unit + PostgreSQL integration)
```

---

## How to run locally

```bash
# Backend — preferred (starts on port 9500)
./run_backend.sh

# Backend — manual (choose your own port)
source activate_and_update_venv.sh
PYTHONPATH=. uvicorn backend.main:app --reload --host 0.0.0.0 --port 9500

# Frontend
cd frontend && npm install && npm run dev
```

**Port contract:**
| Service | Port | Notes |
|---|---|---|
| Backend (`run_backend.sh`) | `9500` | Default; override with `API_PORT=<n>` |
| Frontend Vite dev | `5173` | |
| Frontend Vite preview | `4173` | |
| Frontend API base URL | `http://localhost:9500` | Override with `VITE_API_BASE_URL` |

The `.env.example` shows `API_PORT=8002` — that value is stale; `run_backend.sh` now defaults to **9500**, which matches the frontend's default `VITE_API_BASE_URL`.

**Storage for local dev:** set `APP_STORAGE_BACKEND=json` in `.env` to avoid needing PostgreSQL.

---

## Environment setup

Copy `.env.example` to `.env` and fill in values. Minimum for local dev without any cloud services:

```bash
APP_STORAGE_BACKEND=json
DEBUG=true
SECRET_KEY=local-dev-key
AUTH_ENABLED=false
```

Key env vars (see `.env.example` for the full list):

| Variable | Default | Purpose |
|---|---|---|
| `APP_STORAGE_BACKEND` | `postgres` | `memory` \| `json` \| `postgres` |
| `AUTH_ENABLED` | `true` | Set `false` to skip API key requirement |
| `DEFAULT_ADMIN_KEY` | — | Pre-seeded admin key (skips bootstrap) |
| `DATABASE_URL` | — | `postgresql+psycopg://...` (takes precedence over individual vars) |
| `AZURE_OPENAI_API_KEY` + `_ENDPOINT` + `_DEPLOYMENT` | — | Azure OpenAI provider |
| `GEMINI_API_KEY` | — | Google Gemini provider |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama local provider |
| `OLLAMA_MODEL` | `llama3` | Default Ollama model |
| `GOOGLE_CLIENT_ID` + `_SECRET` | — | Google OAuth for `/auth/google` and ProfilePage |
| `FIGMA_ACCESS_TOKEN` | — | Figma integration for template designer |
| `DEFAULT_MODEL_PROFILE` | auto | `gemini-general` \| `azure-general` \| `ollama-llama3` \| `fallback-fast` |

---

## Key architectural rules

1. **Route handlers stay thin** — all logic lives in the orchestrator, career service, store, or LLM client
2. **Score-based routing** — `can_handle()` returns an `int`; highest score wins; `GeneralistAgent` (score 40) is the catch-all and must always be registered
3. **LLM is optional** — `LLMClient.complete()` and `ModelRouter.complete()` always return a result; callers must handle `used_llm=False`
4. **LLM fallback chain** — `ModelRouter` cascades: Gemini → Ollama → LLaMA-cpp → deterministic fallback; never raises on provider failure
5. **Storage is swappable** — `APP_STORAGE_BACKEND`: `memory` | `json` | `postgres`; swap without changing agent code
6. **Typed contracts** — any API schema change requires updating both `backend/schemas.py` (Pydantic) **and** `frontend/src/types.ts` (TypeScript)
7. **Internal orchestration via ASGI** — the orchestrator calls agents through `InternalPlatformAPI` using httpx ASGI transport, not direct function calls
8. **Prompt versioning** — use `register_prompt()` / `get_prompt()` from `backend/prompt_registry.py`; never hard-code prompt text in agent code
9. **Auth fallback** — when `AUTH_ENABLED=true` but PostgreSQL is unreachable, auth is silently disabled; the `DEFAULT_ADMIN_KEY` always bypasses DB

---

## LLM providers and model profiles

`ModelRouter` selects a provider by profile ID. Available profiles (auto-built from configured env vars):

| Profile ID | Provider | Notes |
|---|---|---|
| `gemini-general` | Google Gemini 2.0 Flash | Requires `GEMINI_API_KEY` |
| `azure-general` | Azure OpenAI | Requires `AZURE_OPENAI_API_KEY` + endpoint + deployment |
| `azure-planner` | Azure OpenAI planner deployment | Optional separate deployment |
| `azure-reviewer` | Azure OpenAI reviewer deployment | Optional separate deployment |
| `ollama-llama3` | Ollama (local) | Requires running Ollama server |
| `llama-cpp-resume` | llama-cpp-python | Requires `LLAMA_RESUME_MODEL_PATH` |
| `fallback-fast` | Deterministic | Always available, returns rule-based output |

---

## Auth system

- **API keys** stored hashed (SHA-256) in PostgreSQL `api_keys` table
- Three roles: `admin` (unrestricted), `operator` (execute + read), `viewer` (read-only)
- All requests pass `X-API-Key: <key>` header; JWT tokens also accepted from `/auth/google`
- **Bootstrap flow**: when no keys exist and `DEFAULT_ADMIN_KEY` is not set, POST `/api-keys/bootstrap` with `BOOTSTRAP_ADMIN_TOKEN` to create the first admin key
- Auth is completely disabled when `AUTH_ENABLED=false` (all requests treated as admin)

---

## Adding a new agent

```python
# 1. Create in agents/
from shared.base_agent import BaseAgent, AgentMetadata, AgentResult

class MyAgent(BaseAgent):
    def __init__(self, ...):
        super().__init__(
            metadata=AgentMetadata(
                name="MyAgent",
                description="What it does",
                capabilities=["keyword1", "keyword2"],
            )
        )

    def can_handle(self, task: str, context=None) -> int:
        return 80 if "keyword" in task.lower() else 0

    def execute(self, task: str, context=None) -> AgentResult:
        return AgentResult(output="...", used_llm=False, metadata={})

# 2. Register in backend/container.py inside build_container()
registry.register(MyAgent(...))
```

If the agent needs LLM access, accept `ollama_client: OllamaClient` and/or `llm_client: LLMClient` in `__init__` — mirror existing agents like `ResumeEvaluatorAgent`.

---

## Known gaps

| ID | Issue | File | Status |
|---|---|---|---|
| G1 | `LLMClient.complete()` live API call not in try/except | `backend/llm_client.py` | **FIXED** |
| G2 | `max_tokens` driven by `MAX_TOKENS` env var (default 2000) | `backend/config.py` | Open — adjust via env |
| G3 | `.env` may have stale Cosmos DB vars from early dev | `.env` | Open — ignore stale vars; `.env.example` is clean |
| G4 | `azure-identity` in requirements but never used | `backend/requirements.txt` | Open |
| G5 | `Dockerfile.backend` missing `PYTHONPATH` env var | `Dockerfile.backend` | **FIXED** |
| G6 | No auth on any endpoint | `backend/main.py` | **FIXED** — RBAC via X-API-Key |
| G7 | No test suite | entire project | **FIXED** — 16 test files |
| G8 | `GeneralistAgent.can_handle()` always returns 40 | `agents/example_agent.py` | Open by design (catch-all) |
| G9 | K8s `secrets.yaml` has placeholder base64 values | `k8s/secrets.yaml` | Open — fill before deploy |
| G10 | No formal migration framework | `backend/migrations/` | Open — SQL files exist; apply manually |
| G11 | `.env.example` shows `API_PORT=8002` but `run_backend.sh` defaults to `9500` | `.env.example` | Open — use 9500 |
| G12 | `services/` microservice stubs are not wired into the main app or test suite | `services/` | Open — future extraction |
| G13 | `backend/data/dev.db` SQLite file is committed to git | `backend/data/dev.db` | Open — add to `.gitignore` |

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

# Smoke test (backend running; AUTH_ENABLED=false or X-API-Key header provided)
curl http://localhost:9500/health
curl -X POST http://localhost:9500/execute \
  -H 'Content-Type: application/json' \
  -d '{"task": "add 3 and 5"}'
```

---

## Test suite overview

| File | Coverage area |
|---|---|
| `test_api.py` | HTTP endpoints via TestClient |
| `test_agents.py` | Agent registry, can_handle scoring |
| `test_auth.py` | API key CRUD, RBAC, bootstrap flow |
| `test_diagnostics.py` | Diagnostics service + agents |
| `test_embeddings_evaluation.py` | Embedding recall evaluation |
| `test_embeddings_service.py` | EmbeddingService unit tests |
| `test_llama.py` | LLaMA / Ollama client stubs |
| `test_llm_adapter.py` | normalize_completion across providers |
| `test_orchestrator.py` | AgentOrchestrator happy/error paths |
| `test_postgres_integration.py` | PostgreSQL integration (skipped if no `DATABASE_URL`) |
| `test_resume_parser.py` | PDF/DOCX extraction, spaCy NER |
| `test_retrieval.py` | RAG retrieval helpers |
| `test_storage.py` | Memory + JSON + Postgres store backends |
| `test_workflow.py` | WorkflowExecutor multi-step flows |

Run PostgreSQL integration tests by setting `DATABASE_URL` (CI does this automatically).
