# Application Knowledge

## Product definition

Actypity is a career intelligence application built on an AI agent orchestration control plane.

The product combines:

- agent orchestration with score-based routing
- multi-provider model routing (Gemini, Azure OpenAI, Ollama, llama-cpp, deterministic fallback)
- local-first resume and JD processing
- ATS keyword analysis, seniority-aware role recommendations, resume Q&A
- recruiter-ready cover letter generation grounded in resume and JD evidence
- recruiter and HR contact discovery from company pages, inferred mailboxes, and LinkedIn lookup flows
- live job search pipeline (Remotive listings + India portal deep-search links)
- per-job ATS fit scoring and improvement recommendations
- multi-turn AI career coaching chatbot with session persistence
- Figma-oriented resume template generation
- PostgreSQL-backed observability, platform state, and career records
- retrieval-backed resume chat context injection for more grounded answers
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
| `backend/career_service.py` | Resume parsing, ATS analysis, chat, job search, live hunt, cover letters, recruiter-contact discovery, template design |
| `backend/database.py` | PostgreSQL client — all platform and career record persistence |
| `backend/embeddings_service.py` | Retrieval index abstraction — FAISS when available, token-index fallback otherwise |
| `backend/retrieval.py` | Thin retrieval wrapper used by resume chat and future RAG paths |
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
| `frontend/src/JobsPage.tsx` | JD extraction, job search, and mounted advanced job-hunt workspace |
| `frontend/src/JobHuntPage.tsx` | Advanced jobs workspace: live hunt, AI hunt, evaluate, write, review |
| `frontend/src/TemplatesPage.tsx` | Template browser and AI design studio (prop-based) |
| `frontend/src/App.css` | Global styles |

Pages:

- **overview** — agent orchestration console, diagnostics, metrics, self-healing status
- **resume** — resume upload/parse, ATS analysis, resume Q&A, evaluate/write/review
- **chat** — multi-turn AI career coaching chatbot
- **jobs** — JD extraction, multi-portal search, live hunt, AI hunt, resume evaluation/writing/review
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

Retrieval state:

- PostgreSQL `resume_embeddings` with `pgvector` for primary semantic retrieval
- hybrid retrieval flow: vector candidates + lexical candidates + application-side reranking
- PostgreSQL `response_quality_metrics` for grounding, citation coverage, confidence, and drift alerts
- `backend/data/embeddings.json`
- `backend/data/embeddings_meta.json`

Important: the application now writes and queries resume embeddings through PostgreSQL `pgvector` when the extension and embedding model are available. The legacy local files remain as a compatibility fallback and migration source, controlled by `RETRIEVAL_LOCAL_FALLBACK_ENABLED`.

Quality and provenance state:

- `/resume/chat` returns citations and confidence from retrieval-backed grounding
- `/resume/cover-letter` returns citations and confidence from resume/JD evidence extraction
- `/job/extract` returns evidence snippets and confidence for manual text and trusted-source extraction
- `/job/recruiter-contacts` returns verified vs inferred counts, confidence, and provenance sources
- `/platform/insights` exposes retrieval metrics plus quality metrics from `response_quality_metrics`
- `/tracker/analytics` now includes quality totals, average grounding score, average citation count, and drift alerts

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
| `GET` | `/platform/insights` | viewer |
| `GET` | `/logs` | viewer |
| `POST` | `/auth/bootstrap` | open (once) |
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
| `GET` | `/diagnostics/reports/latest` | viewer |
| `GET` | `/self-healing/status` | viewer |

### Resume / career

| Method | Path | Auth |
|--------|------|------|
| `POST` | `/resume/parse` | viewer |
| `POST` | `/resume/analyze` | viewer |
| `POST` | `/resume/chat` | viewer |
| `POST` | `/resume/cover-letter` | viewer |
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
| `POST` | `/job/recruiter-contacts` | viewer |
| `POST` | `/jobs/hunt` | viewer |
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
| G13 | `/platform/insights` originally reported scheduler state instead of self-healing state | `backend/main.py` | **FIXED** |
| G14 | Retrieval fallback still relies on local JSON files when pgvector or embeddings are unavailable | `backend/embeddings_service.py`, `backend/embeddings.py` | Open |
| G15 | No prompt registry/versioning for resume, cover-letter, recruiter-contact, and chat prompts | `agents/`, `backend/career_service.py` | Open |
| G16 | No explicit hallucination scoring, citation coverage, or retrieval hit-rate metrics | `backend/metrics.py` | Open |
| G17 | No drift monitoring on job-source quality, ATS scoring quality, or prompt regressions | platform-wide | Open |

---

## Implementation constraints

- Resume/JD/template data stays local whenever Ollama or llama-cpp is available.
- New frontend features must use `frontend/src/api.ts`; never bypass the typed client.
- New backend features must follow route → container → service delegation.
- Platform logs, metrics, agent registry, workflows, and career records stay PostgreSQL-backed.
- Route handlers must not instantiate LLM or scraping clients directly.
- Model profile selection is per-request via `model_profile` field; omitting it uses the default profile.

---

## Additional requirements and enhancement possibilities

- Add saved searches, application pipelines, alerting, and recruiter outreach workspaces per user.
- Add normalized job deduplication across portals so analytics and recommendations are based on canonical opportunities.
- Add source provenance and confidence on JD extraction, recruiter-contact discovery, and resume-chat answers.
- Add `pgvector` or another vector backend so retrieval moves out of local JSON files and becomes multi-user safe.
- Add prompt versioning, rollout control, offline evaluation scores, and rollback metadata.
- Add latency, retrieval, and answer-quality dashboards for production operations.
- Add employer/recruiter feedback capture so resume-fit scoring can improve based on real outcomes.

---

## Accuracy, hallucination, and drift plan

Current state:

- Resume chat now returns retrieval citations and a coarse confidence signal, but grounding is still not a hard trust boundary for every generative endpoint.
- Cover letters and recruiter-contact discovery rely mainly on prompt discipline and heuristics.
- Retrieval metrics are now persisted and surfaced, but answer-faithfulness scoring is still incomplete.

Near-term implementation plan:

1. Add evidence-first response contracts.
Return `sources`, `citations`, and `confidence` fields for resume chat, JD extraction, and recruiter-contact discovery.

2. Add retrieval quality metrics.
Track retrieval hit-rate, empty-context rate, citation coverage, and fallback rate in PostgreSQL.

3. Add prompt governance.
Version prompts used by `career_service` and `chatbot_agent`, persist the prompt version on every execution, and compare quality offline.

4. Add drift monitoring.
Detect changes in job-source freshness, ATS keyword distribution, recruiter-contact discovery confidence, and model-output length/quality trends.

5. Add answer verification.
Run a lightweight critic or rules-based verifier for high-impact outputs like cover letters, recruiter emails, and tailored applications.

---

## Hybrid RAG roadmap

Recommended target architecture:

1. Keep PostgreSQL as the system of record.
2. Add `pgvector` for resumes, JDs, company pages, recruiter pages, and curated job-description chunks.
3. Use hybrid retrieval:
lexical filtering for exact titles, skills, companies, and locations.
semantic retrieval for similarity and paraphrase coverage.
re-ranking for final context selection.
4. Attach provenance to every chunk so the application can show where a recommendation came from.
5. Cache high-value retrieval bundles per user/session to reduce latency and repeated embedding work.

Expected benefits:

- better resume Q&A accuracy
- stronger cover-letter grounding
- better JD understanding across noisy portal text
- lower hallucination risk because evidence becomes mandatory input rather than optional context

---

## Fine-tuning feasibility

Fine-tuning is possible, but it should not be the first quality investment.

Recommended order:

1. prompt versioning
2. retrieval quality and provenance
3. offline evaluation datasets
4. drift monitoring
5. then domain tuning or preference tuning

Best candidates for future tuning:

- resume rewrite style adaptation
- cover-letter tone control
- recruiter-contact ranking
- job-fit explanation style

Avoid tuning before evidence quality is solved, otherwise the system will learn to produce more confident errors rather than better grounded outputs.
