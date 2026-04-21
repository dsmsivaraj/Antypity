# Application Skills

## Role

Operate as a senior frontend and GenAI backend engineer on Antypity.

This means:

- keep the product usable end to end
- preserve typed contracts across backend and frontend
- prefer local/private model execution for sensitive resume and JD workflows
- keep all operational records in PostgreSQL

## Core backend skills

### FastAPI and container wiring

- Keep [backend/main.py](/Users/kdn_aisivarajm/Actypity/backend/main.py:1) thin.
- Put cross-route business logic into [backend/career_service.py](/Users/kdn_aisivarajm/Actypity/backend/career_service.py:1) or other service modules.
- Use `request.app.state.container`; do not create service objects in route handlers.
- If a new capability needs auth, enforce it with `_require(...)` in the route itself.

### Model routing

- Add new profiles in [backend/model_router.py](/Users/kdn_aisivarajm/Actypity/backend/model_router.py:1).
- Use local LLaMA profiles first for resume, JD, and template workloads when available.
- Use Azure OpenAI only when explicit cloud reasoning is required or local models are not available.
- Preserve deterministic fallback behavior.

### Local model engineering

- Ollama integration lives in [backend/local_llm.py](/Users/kdn_aisivarajm/Actypity/backend/local_llm.py:1).
- Direct `gguf` support lives in [backend/llama_client.py](/Users/kdn_aisivarajm/Actypity/backend/llama_client.py:1).
- Do not assume either runtime is available.
- Every local-model call must degrade cleanly to a usable fallback message.

### Resume and JD processing

- File parsing belongs in `CareerService.parse_resume()`.
- Resume scoring, ATS keyword extraction, strengths, and gaps belong in `CareerService.analyze_resume()`.
- Resume Q&A belongs in `CareerService.chat_resume()`.
- Trusted job source extraction and job link generation belong in `CareerService.extract_job_description()` and `CareerService.search_jobs()`.
- Do not scatter resume/job heuristics across route handlers and components.

### Persistence

- New product records must be saved through [backend/database.py](/Users/kdn_aisivarajm/Actypity/backend/database.py:1).
- Do not reintroduce local JSON persistence for product state that already belongs in PostgreSQL.
- If a feature needs analytics, add an explicit DB method instead of computing it in multiple routes.

## Core frontend skills

### API discipline

- All HTTP requests go through [frontend/src/api.ts](/Users/kdn_aisivarajm/Actypity/frontend/src/api.ts:1).
- All frontend shapes live in [frontend/src/types.ts](/Users/kdn_aisivarajm/Actypity/frontend/src/types.ts:1).
- If a backend response changes, update types before updating rendering logic.

### Page design

- The current frontend uses page-state navigation inside [frontend/src/App.tsx](/Users/kdn_aisivarajm/Actypity/frontend/src/App.tsx:1).
- Keep the product organized into:
  - overview (orchestration + diagnostics)
  - resume lab (parse, analyze, Q&A)
  - career chat (multi-turn chatbot — `ChatPage.tsx`, self-managing state)
  - job discovery (`JobsPage.tsx`, state lifted into `App.tsx`)
  - template studio (`TemplatesPage.tsx`, state lifted into `App.tsx`)
- `ChatPage` manages its own state (session, messages, loading). Do not lift chatbot state into `App.tsx`.
- `JobsPage` and `TemplatesPage` are prop-based; update their prop types in the respective `.tsx` file when changing their data contract.
- Use Bootstrap components, but keep the layout opinionated rather than generic.

### Accessibility

- Every input, textarea, file input, and select must have an explicit label with `htmlFor` and `id`.
- New buttons that toggle product state should stay keyboard accessible.
- Do not hide product actions behind icon-only controls unless a text label exists.

## Agent and orchestration skills

- New agents belong in `agents/`.
- Register them in [backend/container.py](/Users/kdn_aisivarajm/Actypity/backend/container.py:1), not in route handlers.
- Use the internal orchestration API path for multi-agent execution instead of direct cross-calls.
- Keep route-to-agent behavior explicit for product-specialized endpoints.

## Figma and template skills

- Template discovery goes through [backend/figma_client.py](/Users/kdn_aisivarajm/Actypity/backend/figma_client.py:1).
- Generated templates should return:
  - section layout
  - design tokens
  - a Figma-ready prompt/brief
- Treat Figma as a design handoff surface, not as the only source of template truth.

## Testing skills

Minimum validation after meaningful changes:

- `./backend/venv/bin/python -m py_compile backend/*.py agents/*.py shared/*.py tests/*.py`
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
- `./backend/venv/bin/pytest tests/test_api.py -q`

For broader backend changes:

- `./backend/venv/bin/pytest tests/test_auth.py tests/test_storage.py tests/test_agents.py tests/test_workflow.py tests/test_orchestrator.py tests/test_diagnostics.py -q`
- `./backend/venv/bin/pytest tests/test_postgres_integration.py -q`

## Bug-fix playbooks

### Backend import or startup break

Check:

- [backend/config.py](/Users/kdn_aisivarajm/Actypity/backend/config.py:1)
- [backend/container.py](/Users/kdn_aisivarajm/Actypity/backend/container.py:1)
- [backend/main.py](/Users/kdn_aisivarajm/Actypity/backend/main.py:1)

### Resume/JD feature bug

Check:

- [backend/career_service.py](/Users/kdn_aisivarajm/Actypity/backend/career_service.py:1)
- [frontend/src/api.ts](/Users/kdn_aisivarajm/Actypity/frontend/src/api.ts:1)
- [frontend/src/App.tsx](/Users/kdn_aisivarajm/Actypity/frontend/src/App.tsx:1)

### Local LLaMA or Ollama bug

Check:

- `LLAMA_*` env vars
- `OLLAMA_*` env vars
- [backend/model_router.py](/Users/kdn_aisivarajm/Actypity/backend/model_router.py:1)
- [backend/llama_client.py](/Users/kdn_aisivarajm/Actypity/backend/llama_client.py:1)
- [backend/local_llm.py](/Users/kdn_aisivarajm/Actypity/backend/local_llm.py:1)

### Trusted job source bug

Check:

- allowlist in `CareerService`
- search URL construction
- frontend source selection state
- whether the issue is JD extraction or search-link generation

### Chatbot not responding or losing session

Check:

- `OLLAMA_BASE_URL` and `OLLAMA_MODEL` env vars (Ollama is tried first)
- `container.chat_store` is a single shared `ChatStore()` instance — do not reinstantiate it per request
- Session key: `sessionStorage.getItem('actypity_chat_session')` in the browser
- Route is `POST /chat` (no auth required) — check CORS if cross-origin errors appear
- `ChatbotAgent` name must be `"career-chatbot"` as registered in `container.py`
