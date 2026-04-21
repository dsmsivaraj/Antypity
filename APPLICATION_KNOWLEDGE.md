# Application Knowledge

## Product definition

Actypity is a career intelligence application built on an AI agent orchestration control plane.

The product combines:

- agent orchestration with score-based routing
- multi-provider model routing (Gemini, Azure OpenAI, Ollama, llama-cpp, deterministic fallback)
- local-first resume and JD processing
- ATS keyword analysis, seniority-aware role recommendations, resume Q&A
- live job search pipeline (Remotive listings + India portal deep-search links)
- per-job ATS fit scoring and improvement recommendations
- multi-turn AI career coaching chatbot with session persistence
- Figma-oriented resume template generation
- PostgreSQL-backed observability, platform state, and career records
- in-process self-healing controller with diagnostics loop

---

## Current architecture

### Backend

Primary entry points:

| File | Responsibility |
|------|---------------|
| `backend/main.py` | FastAPI route registration, auth/RBAC enforcement, lifespan hooks |
| `backend/container.py` | App container wiring — all clients, services, agents, and scheduler |
| `backend/config.py` | Settings dataclass, env var parsing, feature flags |
| `backend/model_router.py` | Model catalog, profile-based routing across all LLM providers |
| `backend/career_service.py` | Resume parsing, ATS analysis, chat, job search, live hunt, template design |
| `backend/database.py` | PostgreSQL client — all platform and career record persistence |
| `backend/gemini_client.py` | Google Gemini REST API client (`X-goog-api-key`, `generateContent`) |
| `backend/llm_client.py` | Azure OpenAI client with try/except safety |
| `backend/local_llm.py` | Ollama inference client |
| `backend/llama_client.py` | Direct `.gguf` inference via `llama-cpp-python` |
| `backend/figma_client.py` | Figma API client for template metadata |
| `backend/self_healing.py` | `InProcessSelfHealingController` — asyncio background diagnostics loop |
| `backend/job_search_service.py` | `LiveJobSearchService` — Remotive + portal deep-search link builder |
| `backend/auth.py` | `AuthService` — X-API-Key RBAC, key seeding, permission checking |
| `backend/metrics.py` | `MetricsService` — execution and agent metrics |
| `backend/scheduler.py` | `DiagnosticsScheduler` — periodic diagnostics runner |
| `backend/storage.py` | `ExecutionStore` — swappable memory / JSON / PostgreSQL backend |
| `backend/schemas.py` | All Pydantic request/response schemas |
| `backend/internal_api.py` | `InternalPlatformAPI` — ASGI transport for orchestrator→agent calls |

### Frontend

Primary files:

| File | Responsibility |
|------|---------------|
| `frontend/src/App.tsx` | App shell, page-state navigation, Overview and Resume pages |
| `frontend/src/api.ts` | Typed HTTP client for all backend endpoints |
| `frontend/src/types.ts` | All shared TypeScript interfaces |
| `frontend/src/ChatPage.tsx` | Multi-turn chatbot page (self-managing state) |
| `frontend/src/JobsPage.tsx` | JD extraction, job search, live job hunt (prop-based) |
| `frontend/src/JobHuntPage.tsx` | Live job hunt tab with ATS-scored listings and portal links |
| `frontend/src/TemplatesPage.tsx` | Template browser and AI design studio (prop-based) |
| `frontend/src/App.css` | Global styles |

Pages:

- **overview** — agent orchestration console, diagnostics, metrics, self-healing status
- **resume** — resume upload/parse, ATS analysis, resume Q&A, evaluate/write/review
- **chat** — multi-turn AI career coaching chatbot
- **jobs** — JD extraction, multi-portal search link generation, live job hunt
- **templates** — template browser and AI template design studio

---

## Model architecture

### Provider priority (auto-select order)

```
1. Google Gemini   — if GEMINI_API_KEY is set
2. Azure OpenAI    — if AZURE_OPENAI_DEPLOYMENT is set
3. Ollama          — if Ollama is running at OLLAMA_BASE_URL
4. Deterministic   — always available, no LLM required
```

Override with `DEFAULT_MODEL_PROFILE=<profile-id>` in `.env`.

### Model profiles

#### Google Gemini (provider: `gemini`)

| Profile ID | Model | Mode |
|-----------|-------|------|
| `gemini-general` | `GEMINI_MODEL` (default: `gemini-2.0-flash`) | balanced |
| `gemini-resume` | `GEMINI_MODEL` | resume/ATS |
| `gemini-pro` | `gemini-2.5-pro-preview-05-06` | pro/complex |
| `gemini-flash` | `gemini-2.0-flash` | fast |

Requires: `GEMINI_API_KEY` (paid tier — free tier quota is 0).

#### Azure OpenAI (provider: `azure-openai`)

| Profile ID | Deployment env var | Mode |
|-----------|-------------------|------|
| `azure-general` | `AZURE_OPENAI_DEPLOYMENT` | balanced |
| `azure-planner` | `AZURE_OPENAI_PLANNER_DEPLOYMENT` | planner |
| `azure-reviewer` | `AZURE_OPENAI_REVIEWER_DEPLOYMENT` | critic |

Requires: `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`.
Note: current Azure resource only has DALL-E/Whisper — chat completion deployment is disabled.

#### Ollama local (provider: `ollama/<model>`)

| Profile ID | Mode |
|-----------|------|
| `ollama-<model>` | local-balanced |
| `ollama-resume` | local-resume |
| `ollama-chat` | local-chat |

Requires: Ollama running at `OLLAMA_BASE_URL` with `OLLAMA_MODEL` pulled.
Current: `llama3.1` at `http://localhost:11434`.

#### llama-cpp local (provider: `llama-cpp`)

| Profile ID | Env var | Mode |
|-----------|---------|------|
| `llama-local-general` | `LLAMA_MODEL_PATH` | local-balanced |
| `llama-local-resume` | `LLAMA_RESUME_MODEL_PATH` | local-resume |
| `llama-local-jd` | `LLAMA_JOB_MODEL_PATH` | local-job |
| `llama-local-template` | `LLAMA_TEMPLATE_MODEL_PATH` | local-design |

Requires: `.gguf` model file at configured path.

#### Deterministic fallback (provider: `fallback`)

| Profile ID | Mode |
|-----------|------|
| `fallback-fast` | fast |
| `fallback-critic` | critic |

Always available. No LLM calls — returns rule-based responses.

---

## Agent architecture

Registered agents (17 total):

| Agent class | Name | Score signal |
|------------|------|-------------|
| `GeneralistAgent` | `generalist` | 40 (catch-all) |
| `PlannerAgent` | `planner` | keyword-based |
| `ReviewerAgent` | `reviewer` | keyword-based |
| `MathAgent` | `math` | math keywords |
| `LocalResumeAgent` | `local-resume-analyzer` | resume keywords |
| `LocalJDAgent` | `local-jd-analyzer` | JD keywords |
| `ResumeTemplateAgent` | `resume-template-advisor` | template keywords |
| `ChatbotAgent` | `career-chatbot` | chat keywords |
| `EnhancedJobSearchAgent` | `job-search` | job search keywords |
| `ResumeEvaluatorAgent` | `resume-evaluator` | evaluate keywords |
| `ResumeWriterAgent` | `resume-writer` | write keywords |
| `ResumeReviewerAgent` | `resume-reviewer` | review keywords |
| `JobApplicantAgent` | `job-applicant` | applicant keywords |
| `HealthCheckAgent` | `health-monitor` | health keywords |
| `TestRunnerAgent` | `test-runner` | test keywords |
| `CodeAnalyzerAgent` | `code-analyzer` | code keywords |
| `DiagnosticsReporterAgent` | `diagnostics-reporter` | diagnostics keywords |

---

## Persistence map

Platform tables (PostgreSQL):

- `executions`
- `api_keys`
- `agent_registry`
- `execution_logs`
- `agent_metrics`
- `workflow_definitions`
- `workflow_executions`
- `diagnostic_runs`

Career tables (PostgreSQL):

- `resume_analyses`
- `resume_templates`
- `career_queries`
- `job_search_results`

User tables (PostgreSQL):

- `users`
- `user_sessions`
- `user_profiles`

---

## Trusted job sources

Controlled by `TRUSTED_JOB_SOURCES` env var. Current catalog:

`linkedin, indeed, glassdoor, wellfound, naukri, foundit, careerbuilder, dice, ziprecruiter, remoteok, stackoverflow, github`

Live job hunt pipeline:
- **Remotive API** (`https://remotive.com/api/remote-jobs`) — real listings, fetches all ~21 jobs, ranks by ATS keyword match
- **Portal deep-search links** — Naukri, LinkedIn, Indeed India, Wellfound with experience-band URL filters
- `result_type: "listing"` = real Remotive job | `result_type: "portal_search"` = deep-search link

---

## Self-healing

`InProcessSelfHealingController` runs an asyncio background loop (default 300s interval):

1. Run `DiagnosticsService.run_full_diagnostics()`
2. For each issue: attempt repair (DB reconnect, advisory logging)
3. Verify — re-run health check
4. Record cycle in history (last 50 cycles retained)

Status via `GET /self-healing/status`. Manual trigger via `POST /self-healing/trigger`.
Does not proxy to an external port — runs fully in-process.

---

## Runtime contract

| Service | URL |
|---------|-----|
| Backend | `http://localhost:9500` |
| Frontend Vite dev | `http://localhost:5173` |
| Frontend preview | `http://localhost:4173` |
| Ollama | `http://localhost:11434` |

`frontend/src/api.ts` defaults to `http://localhost:9500`.
`run_backend.sh` also starts on `9500`.

---

## Key API surface

### Platform

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/health` | open |
| `GET` | `/ready` | open |
| `GET` | `/agents` | viewer |
| `GET` | `/models` | viewer |
| `POST` | `/execute` | viewer |
| `GET` | `/executions` | viewer |
| `GET` | `/metrics` | viewer |
| `GET` | `/logs` | viewer |
| `POST` | `/bootstrap` | open (once) |
| `POST` | `/auth/keys` | admin |
| `GET` | `/auth/keys` | admin |
| `DELETE` | `/auth/keys/{id}` | admin |
| `GET` | `/auth/status` | open |

### Workflows

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/workflows/definitions` | viewer |
| `GET` | `/workflows/definitions` | viewer |
| `POST` | `/workflows/execute` | viewer |
| `GET` | `/workflows/executions` | viewer |

### Diagnostics & self-healing

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/diagnostics/run` | viewer |
| `GET` | `/diagnostics/reports` | viewer |
| `GET` | `/diagnostics/latest` | viewer |
| `GET` | `/self-healing/status` | open |
| `POST` | `/self-healing/trigger` | viewer |

### Resume / career

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/resume/parse` | viewer |
| `POST` | `/resume/analyze` | viewer |
| `POST` | `/resume/chat` | viewer |
| `GET` | `/resume/templates` | viewer |
| `POST` | `/resume/templates/design` | viewer |
| `POST` | `/resume/evaluate` | viewer |
| `POST` | `/resume/write` | viewer |
| `POST` | `/resume/review` | viewer |
| `GET` | `/tracker/analytics` | viewer |

### Jobs

| Method | Path | Auth |
|--------|------|------|
| `GET` | `/job/sources` | viewer |
| `POST` | `/job/extract` | viewer |
| `POST` | `/job/search` | viewer |
| `POST` | `/resume/hunt` | viewer |
| `POST` | `/jobs/live-hunt` | viewer |

### Chat

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/chat` | open |
| `GET` | `/chat/history/{session_id}` | open |
| `DELETE` | `/chat/session/{session_id}` | open |

### Ollama / internal

| Method | Path |
|--------|------|
| `GET` | `/ollama/status` |
| `GET` | `/internal/models` |
| `POST` | `/internal/complete` |
| `POST` | `/internal/agent/score` |
| `POST` | `/internal/agent/execute` |

---

## Known gaps

| ID | Issue | File | Status |
|----|-------|------|--------|
| G1 | `LLMClient.complete()` live API call not in try/except | `backend/llm_client.py` | **FIXED** |
| G2 | `max_tokens` default 2000 → now 4000 via `MAX_TOKENS` env | `backend/config.py` | **FIXED** |
| G3 | `.env` had stale Cosmos DB vars | `.env` | **FIXED** — removed |
| G4 | `azure-identity` in requirements but never used | `backend/requirements.txt` | Open |
| G5 | `Dockerfile.backend` missing `PYTHONPATH` env var | `Dockerfile.backend` | **FIXED** |
| G6 | No auth on any endpoint | `backend/main.py` | **FIXED** — RBAC via X-API-Key |
| G7 | No test suite | entire project | **FIXED** — 99 tests |
| G8 | `GeneralistAgent.can_handle()` always returns 40 | `agents/example_agent.py` | Open by design (catch-all) |
| G9 | K8s `secrets.yaml` has placeholder base64 values | `k8s/secrets.yaml` | Open — fill before deploy |
| G10 | No formal migration framework | `backend/database.py` | Open |
| G11 | Gemini API key on free tier — quota limit is 0 | `.env` | Open — needs paid billing |
| G12 | Remotive free API returns only ~21 jobs (fixed pool) | `backend/job_search_service.py` | Open — use RapidAPI for scale |

---

## Implementation constraints

- Resume/JD/template data stays local whenever Ollama or llama-cpp is available.
- New frontend features must use `frontend/src/api.ts`; never bypass the typed client.
- New backend features must follow route → container → service delegation.
- Platform logs, metrics, agent registry, workflows, and career records stay PostgreSQL-backed.
- Route handlers must not instantiate LLM or scraping clients directly.
- Model profile selection is per-request via `model_profile` field; omitting it uses the default profile.
