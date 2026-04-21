# Application Skills

## Role

Operate as a senior GenAI backend and frontend engineer on Actypity.

This means:

- keep the product usable end to end
- preserve typed contracts across backend and frontend
- prefer local/private model execution (Ollama, llama-cpp) for sensitive resume and JD workflows
- use Gemini as the primary cloud LLM when billing is active; fall back to Ollama automatically
- keep all operational and career records in PostgreSQL

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
- Live job hunt → `CareerService.live_hunt_jobs()` → `LiveJobSearchService`.
- Job fit scoring → `CareerService._analyze_job_fit()` (keyword intersection, match %, matched/missing keywords, improvement areas).
- Template design → `CareerService.design_template()`.
- Do not scatter resume/job heuristics across route handlers.

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
- **job discovery** — `JobsPage.tsx` + `JobHuntPage.tsx` (state in `App.tsx`)
- **template studio** — `TemplatesPage.tsx` (state in `App.tsx`)

Rules:
- `ChatPage` manages its own session/message/loading state. Do not lift chatbot state into `App.tsx`.
- `JobsPage` and `TemplatesPage` are prop-based; update their prop types when changing their data contract.
- Use Bootstrap components, but keep the layout opinionated rather than generic.

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
- Bootstrap route: `POST /bootstrap` with `BOOTSTRAP_ADMIN_TOKEN` to create first admin key
