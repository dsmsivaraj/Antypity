# Application Skills

## Role

Operate as a senior GenAI backend and frontend engineer on Actypity.

This means:

- keep the product usable end to end
- preserve typed contracts across backend and frontend
- prefer local/private model execution (Ollama, llama-cpp) for sensitive resume and JD workflows
- use Gemini as the primary cloud LLM when billing is active; fall back to Ollama automatically
- keep all operational and career records in PostgreSQL
- keep cover letters, recruiter-contact discovery, and job-fit guidance grounded in resume/JD evidence rather than generic prose

---

## Core backend skills

### FastAPI and container wiring

- Keep `backend/main.py` thin — route registration, auth guards, and lifespan only.
- Put all business logic in `backend/career_service.py` or other service modules.
- Use `request.app.state.container`; never instantiate service objects inside route handlers.
- If a new capability needs auth, enforce it with `_require(...)` in the route itself.

### Model routing

Profiles and routing live in `backend/model_router.py`. Rules:

- Add new profiles in `_build_profiles()`. Insert at `[0]` so higher-priority providers win.
- Set `DEFAULT_MODEL_PROFILE` in `.env` to pin a specific profile for all requests.
- Omit `DEFAULT_MODEL_PROFILE` to let auto-select run: Gemini → Azure → Ollama → fallback.
- Per-request override: pass `model_profile=<id>` in the request body.
- Every `complete()` call must handle `used_llm=False` — the router never raises on LLM failure.

Provider routing in `complete()`:

| `profile.provider` | Client used |
|--------------------|-------------|
| `"gemini"` | `GeminiClient.complete()` — falls back to Ollama if Gemini disabled |
| `"azure-openai"` | `LLMClient.complete()` with deployment |
| `"llama-cpp"` | `LocalLlamaClient.complete()` |
| `"ollama/*"` | `OllamaClient.complete()` |
| `"fallback"` | `LLMClient.complete()` with no deployment (deterministic) |

### Google Gemini

- `GeminiClient` lives in `backend/gemini_client.py`.
- REST endpoint: `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- Auth header: `X-goog-api-key` (not Bearer).
- System prompt goes in `body["system_instruction"]`, not in `contents`.
- `enabled = bool(api_key)` — client disables itself cleanly when key is absent.
- **Free tier quota is 0** — requires a paid Google AI / Cloud billing account to function.
- Changing the model: set `GEMINI_MODEL=gemini-2.5-pro-preview-05-06` in `.env` or pass `model=` in `complete()`.

### Ollama (local LLM)

- Client in `backend/local_llm.py`.
- Configured via `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
- Current model: `llama3.1` at `http://localhost:11434`.
- `enabled` is set at startup by probing `/api/tags`; agents that depend on it check `ollama_client.enabled` before calling.
- Every Ollama call must degrade cleanly if Ollama is not running.

### llama-cpp (direct .gguf inference)

- Client in `backend/llama_client.py`.
- Configured via `LLAMA_MODEL_PATH` (and per-domain variants `LLAMA_RESUME_MODEL_PATH`, etc.).
- `enabled` is `True` only when at least one path is set.
- Direct GGUF inference — no network required.

### Resume and JD processing

- File parsing → `CareerService.parse_resume()` (PDF via pypdf + `_fix_pdf_text()` for spacing repair).
- Resume scoring, ATS keyword extraction, seniority detection, role recommendations → `CareerService.analyze_resume()`.
- Seniority is detected from VP/Director/Manager keywords and year-count heuristics; role recommendations are tiered (VP/Director/Manager/IC × domain).
- Resume Q&A → `CareerService.chat_resume()`.
- Cover letter generation → `CareerService.create_cover_letter()`.
- Recruiter / HR contact discovery → `CareerService.discover_recruiter_contacts()`.
- Live job hunt → `CareerService.live_hunt_jobs()` → `LiveJobSearchService`.
- Job fit scoring → `CareerService._analyze_job_fit()` (keyword intersection, match %, matched/missing keywords, improvement areas).
- Template design → `CareerService.design_template()`.
- Do not scatter resume/job heuristics across route handlers.

### Cover letters

- Generate cover letters through `POST /resume/cover-letter`.
- Keep them evidence-based: only claims that are supported by the resume or JD context.
- Subject line, concise body, and talking points should all be returned.
- Avoid generic enthusiasm paragraphs and avoid inventing domain expertise the candidate does not show.

### Recruiter and HR contacts

- Use `POST /job/recruiter-contacts` for structured discovery.
- Priority order:
  1. emails explicitly found in provided text
  2. emails scraped from official company pages (`/careers`, `/contact`, `/about`, `/team`)
  3. inferred mailbox patterns such as `careers@company.com` with low confidence
- Always distinguish discovered contacts from inferred contacts.
- Always return trusted lookup URLs, especially official company pages and LinkedIn people/company search paths.

### Live job hunt pipeline

- `LiveJobSearchService` in `backend/job_search_service.py`.
- `_fetch_remotive_all()`: fetches all ~21 jobs from `https://remotive.com/api/remote-jobs`, ranks by ATS match score.
- `_build_portal_links()`: builds Naukri, LinkedIn, Indeed India, Wellfound deep-search URLs with experience-band filters.
- `result_type: "listing"` = real job (has `apply_url`); `result_type: "portal_search"` = portal deep-search URL.
- To scale beyond 21 jobs: integrate RapidAPI JSearch (`RAPIDAPI_KEY`).

### Self-healing

- `InProcessSelfHealingController` in `backend/self_healing.py`.
- Runs an asyncio background task (default 300s interval) calling `DiagnosticsService.run_full_diagnostics()`.
- Repair actions: DB reconnect, advisory/critical logging per issue severity.
- Exposes `get_status()` (dict with `is_running`, `cycle_count`, `last_cycle_at`, `history`).
- Started/stopped in the FastAPI lifespan in `main.py`. Never proxy to an external port.

### Persistence

- New product records must be saved through `backend/database.py`.
- Do not reintroduce local JSON persistence for product state that belongs in PostgreSQL.
- If a feature needs analytics, add an explicit DB method instead of computing it across routes.

### Retrieval and grounding

- The primary retrieval path is PostgreSQL `pgvector` when the extension and embedding model are available.
- The legacy local index is still present as a fallback and migration source. Do not remove it unless every target environment has pgvector and embedding-model support.
- Retrieval now uses hybrid candidate selection: vector retrieval plus lexical matching with application-side reranking.
- If you change resume chat, JD extraction, or recruiter-contact discovery, prefer adding explicit provenance fields instead of longer prose.
- `backend/embeddings_service.py` is the current retrieval entry point. If you improve retrieval, do it there first rather than adding one-off embedding logic in feature services.
- The next production-grade step is hybrid RAG with PostgreSQL + `pgvector`, lexical filters, and re-ranking.
- Persist grounding and drift signals in PostgreSQL instead of calculating them only in memory. `response_quality_metrics` is now the system of record for quality summaries.
- New grounded outputs should return both evidence (`citations` or `provenance`) and an explicit confidence label. Avoid responses that read authoritative without showing what grounded them.

### Prompt governance

- Career prompts in `backend/career_service.py` and `agents/chatbot_agent.py` are product logic. Treat them like versioned business rules.
- Avoid silently broadening prompts in ways that encourage unsupported claims.
- Prefer prompts that require evidence from the resume, JD, or trusted source text.
- If a response is retrieval-backed, preserve or improve the returned citations rather than stripping them for brevity.
- When you change prompts, add or update tests for response shape and fallback behavior.

### Hallucination and drift reduction

- Prefer evidence extraction before generation.
- Separate discovered facts from inferred suggestions, especially for recruiter-contact discovery.
- Add metrics for retrieval hit-rate, empty-context rate, citation coverage, and fallback usage before considering fine-tuning.
- Treat inferred contacts, low-evidence cover letters, and short/noisy job descriptions as drift-prone responses. Mark them low confidence and record a drift flag.
- Fine-tuning should follow prompt versioning, eval datasets, and retrieval quality work, not replace them.

---

## Core frontend skills

### API discipline

- All HTTP requests go through `frontend/src/api.ts`.
- All frontend shapes live in `frontend/src/types.ts`.
- If a backend response changes, update `types.ts` before updating rendering logic.

### Page design

The frontend uses page-state navigation inside `App.tsx`. Pages:

- **overview** — orchestration console, diagnostics, self-healing status
- **resume lab** — parse, analyze, Q&A, evaluate/write/review
- **career chat** — `ChatPage.tsx` (self-managing state — do not lift into `App.tsx`)
- **job discovery** — `JobsPage.tsx` plus embedded `JobHuntPage.tsx` for advanced live hunt / evaluate / write / review flows
- **template studio** — `TemplatesPage.tsx` (state in `App.tsx`)

Rules:
- `ChatPage` manages its own session/message/loading state. Do not lift chatbot state into `App.tsx`.
- `JobsPage` and `TemplatesPage` are prop-based; update their prop types when changing their data contract.
- `JobHuntPage` is intentionally mounted inside `JobsPage`; if you change its props or API contracts, validate the parent integration, not just the standalone component.
- Use Bootstrap components, but keep the layout opinionated rather than generic.
- Keep overview and monitoring surfaces useful for operators. Platform metrics, retrieval state, and self-healing status belong in the UI when they drive troubleshooting.
- Retrieval metrics shown in the UI should come from the backend analytics contract, not from frontend-derived estimates.

### Accessibility

- Every input, textarea, file input, and select must have an explicit label with `htmlFor` and `id`.
- New buttons that toggle state must be keyboard accessible.
- Do not hide product actions behind icon-only controls unless a text label exists.

---

## Agent and orchestration skills

- New agents belong in `agents/`.
- Register them in `backend/container.py`, not in route handlers.
- Use the internal ASGI transport API (`InternalPlatformAPI`) for multi-agent execution — never direct cross-calls.
- Keep route-to-agent behavior explicit for product-specialized endpoints.

---

## Figma and template skills

- Template discovery goes through `backend/figma_client.py`.
- Generated templates must return: section layout, design tokens, and a Figma-ready brief.
- Treat Figma as a design handoff surface, not the only source of template truth.

---

## Testing skills

Minimum validation after meaningful changes:

```bash
# Backend compile + import
PYTHONPATH=. python -m py_compile backend/main.py backend/container.py backend/config.py \
  backend/model_router.py backend/gemini_client.py backend/career_service.py \
  backend/self_healing.py backend/job_search_service.py \
  agents/agent_orchestrator.py agents/agent_registry.py shared/base_agent.py
PYTHONPATH=. python -c "from backend.main import app; print('ok')"

# Full test suite
PYTHONPATH=. pytest tests/ -q

# Frontend
cd frontend && npm run lint && npm run build
```

Smoke test (backend running):

```bash
curl http://localhost:9500/health
curl -H "X-API-Key: act_local_admin" http://localhost:9500/models
curl -H "X-API-Key: act_local_admin" http://localhost:9500/platform/insights
curl -H "X-API-Key: act_local_admin" -X POST http://localhost:9500/execute \
  -H 'Content-Type: application/json' \
  -d '{"task": "add 3 and 5"}'
```

---

## Bug-fix playbooks

### Backend import or startup break

Check in order:
1. `backend/config.py` — missing field or bad default
2. `backend/container.py` — wrong constructor args
3. `backend/main.py` — lifespan or route registration error

### Model returning errors or wrong provider

Check:
1. `DEFAULT_MODEL_PROFILE` in `.env` — is it a valid profile ID?
2. `backend/model_router.py` `_default_profile()` — which provider wins?
3. Gemini 429: free-tier quota exhausted — enable billing at Google AI Studio
4. Azure 404: deployment name missing or resource has no chat model — comment out `AZURE_OPENAI_DEPLOYMENT`
5. Ollama not responding: run `ollama serve` and `ollama pull llama3.1`

### Resume/JD feature bug

Check:
- `backend/career_service.py` — `_fix_pdf_text()`, `_detect_seniority()`, `_recommend_roles()`
- `frontend/src/api.ts` — request/response shape
- `frontend/src/App.tsx` or `frontend/src/JobsPage.tsx` — rendering logic

### Live job hunt returning no results

Check:
- Remotive API reachable: `curl https://remotive.com/api/remote-jobs?limit=5`
- `backend/job_search_service.py` `_fetch_remotive_all()` — network timeout?
- Portal links are always generated even when Remotive fails

### Chatbot not responding or losing session

Check:
- `OLLAMA_BASE_URL` and `OLLAMA_MODEL` env vars
- `container.chat_store` is a single `ChatStore()` — never reinstantiate per request
- Session key: `sessionStorage.getItem('actypity_chat_session')` in the browser
- Route is `POST /chat` — check CORS if cross-origin errors appear
- The system prompt in `agents/chatbot_agent.py` now covers job filtering, cover letters, and recruiter-contact guidance; update that prompt before adding ad hoc route-side instructions.

### Cover letter output is weak or generic

Check:
- `CareerService.create_cover_letter()` prompt and parser
- Resume/JD excerpts passed into the request
- `DEFAULT_MODEL_PROFILE` or request `model_profile`
- Whether the response still contains a `Subject:` line and `Talking Points:` section

### Recruiter contact discovery returns poor results

Check:
- Official company domain passed into `/job/recruiter-contacts`
- Company page fetchability (`/careers`, `/contact`, `/about`, `/team`)
- Whether contacts are discovered or inferred
- Lookup URLs returned for LinkedIn/company research

### Platform insights look wrong

Check:
- `GET /platform/insights` against the live backend
- `backend/main.py` — ensure self-healing status comes from `container.self_healing`, not the diagnostics scheduler
- `backend/embeddings_service.py` — verify retrieval backend and document counts
- `frontend/src/App.tsx` — verify the overview page is rendering the latest platform insights state

### Self-healing not running

Check:
- `container.self_healing.get_status()` — is `is_running: true`?
- Lifespan in `main.py` — `self_healing.start()` called in startup
- `backend/self_healing.py` — asyncio loop not crashing silently (check logs)
- `CodeAnalyzerAgent` skipping venv dirs — `_SKIP_DIRS` in `agents/diagnostics_agent.py`

### Auth / RBAC error

Check:
- `X-API-Key` header is present
- Key is seeded: `DEFAULT_ADMIN_KEY=act_local_admin` in `.env`
- `AUTH_ENABLED=true` — set to `false` for local dev without key management
- Bootstrap route: `POST /auth/bootstrap` with `X-Bootstrap-Token` to create the first admin key
