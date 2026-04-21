# Application Knowledge

## Product definition

Antypity is a career intelligence application built on the existing Actypity control-plane foundation.

The current product combines:

- agent orchestration
- model routing
- local file processing
- resume and JD understanding
- resume chatbot workflows
- trusted job source discovery
- Figma-oriented resume template generation
- PostgreSQL-backed observability and platform state

## Current architecture

### Backend

Primary backend entry points:

- [backend/main.py](/Users/kdn_aisivarajm/Actypity/backend/main.py:1)
- [backend/container.py](/Users/kdn_aisivarajm/Actypity/backend/container.py:1)
- [backend/config.py](/Users/kdn_aisivarajm/Actypity/backend/config.py:1)
- [backend/database.py](/Users/kdn_aisivarajm/Actypity/backend/database.py:1)
- [backend/model_router.py](/Users/kdn_aisivarajm/Actypity/backend/model_router.py:1)
- [backend/career_service.py](/Users/kdn_aisivarajm/Actypity/backend/career_service.py:1)

Responsibilities:

- `main.py`
  Owns FastAPI route registration and auth/RBAC enforcement.
- `container.py`
  Wires the app container, registry, orchestrator, model router, Ollama, local LLaMA, Figma, and the career service.
- `career_service.py`
  Owns resume parsing, resume analysis, resume chat, trusted job source discovery, JD extraction, template generation, and career analytics.
- `database.py`
  Stores platform records and career artifacts in PostgreSQL.
- `model_router.py`
  Exposes the model catalog and routes requests across fallback, Azure OpenAI, and local LLaMA profiles.
- `local_llm.py`
  Wraps Ollama for local model inference.
- `llama_client.py`
  Wraps `llama-cpp-python` for direct local `.gguf` inference.
- `figma_client.py`
  Reads Figma-backed or community template metadata.

### Frontend

Primary frontend files:

- [frontend/src/App.tsx](/Users/kdn_aisivarajm/Actypity/frontend/src/App.tsx:1)
- [frontend/src/api.ts](/Users/kdn_aisivarajm/Actypity/frontend/src/api.ts:1)
- [frontend/src/types.ts](/Users/kdn_aisivarajm/Actypity/frontend/src/types.ts:1)
- [frontend/src/App.css](/Users/kdn_aisivarajm/Actypity/frontend/src/App.css:1)

The current frontend is a Bootstrap application with four main pages implemented through page-state navigation:

- `overview`
- `resume`
- `jobs`
- `templates`

## Model architecture

### Cloud models

Azure OpenAI profiles:

- `azure-general`
- `azure-planner`
- `azure-reviewer`

### Local models

`llama-cpp-python` profiles:

- `llama-local-general`
- `llama-local-resume`
- `llama-local-jd`
- `llama-local-template`

Ollama-backed agents:

- `local-resume-analyzer`
- `local-jd-analyzer`
- `resume-template-advisor`
- `career-chatbot`
- `job-search`

Model routing behavior:

- prefer local LLaMA for private resume/JD/template processing when configured
- use Ollama-backed agents for local agent execution when Ollama is running
- use Azure OpenAI when explicitly configured
- fall back to deterministic responses when no live model is available

## Agent architecture

Current registered agent families:

- core orchestration agents
  - `generalist`
  - `planner`
  - `reviewer`
  - `math`
- local career agents
  - `local-resume-analyzer`
  - `local-jd-analyzer`
  - `resume-template-advisor`
  - `career-chatbot`
  - `job-search`
- diagnostics agents
  - `health-monitor`
  - `test-runner`
  - `code-analyzer`
  - `diagnostics-reporter`

## Persistence map

Platform tables already in PostgreSQL:

- `executions`
- `api_keys`
- `agent_registry`
- `execution_logs`
- `agent_metrics`
- `workflow_definitions`
- `workflow_executions`
- `diagnostic_runs`

Career tables now in PostgreSQL:

- `resume_analyses`
- `resume_templates`
- `career_queries`
- `job_search_results`

User and ATS-oriented tables already present in the schema:

- `users`
- `user_sessions`
- `user_profiles`

## Trusted job sources

The current trusted-source catalog is environment-driven through `TRUSTED_JOB_SOURCES` and supports:

- LinkedIn
- Indeed
- Glassdoor
- Wellfound
- Naukri
- Dice
- ZipRecruiter

The app treats these as trusted discovery sources and generates search links against them. JD extraction accepts only allowlisted portal URLs or manually pasted JD text.

## Runtime contract

- Backend local: `http://localhost:9500`
- Frontend local: `http://localhost:5173`
- Ollama local: `http://localhost:11434`

`frontend/src/api.ts` defaults to `http://localhost:9500`, so [run_backend.sh](/Users/kdn_aisivarajm/Actypity/run_backend.sh:1) must stay aligned unless `VITE_API_BASE_URL` is overridden.

## Key API surface

Platform:

- `GET /health`
- `GET /ready`
- `GET /agents`
- `GET /models`
- `POST /execute`
- `GET /executions`
- `GET /metrics`
- `GET /logs`

Career:

- `POST /resume/parse`
- `POST /resume/analyze`
- `POST /resume/chat`
- `GET /resume/templates`
- `POST /resume/templates/design`
- `GET /job/sources`
- `POST /job/extract`
- `POST /job/search`
- `GET /tracker/analytics`
- `POST /chat`
- `GET /chat/history/{session_id}`

## Implementation constraints

- Resume/JD/template data should stay local whenever a local model path or Ollama runtime is available.
- New frontend features must use `frontend/src/api.ts`; do not bypass the typed client.
- New backend features must prefer route -> container -> service delegation.
- Platform logs, metrics, agent registry, workflows, and new career records must stay PostgreSQL-backed.
- Route handlers should not instantiate LLM or scraping clients directly.
