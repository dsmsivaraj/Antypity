# Application Workflow

## 1. Platform bootstrap

1. Start PostgreSQL, or point `DATABASE_URL` to an existing instance.
2. Start the backend with [run_backend.sh](/Users/kdn_aisivarajm/Actypity/run_backend.sh:1).
3. Start the frontend with `npm run dev` in `frontend/`.
4. Frontend loads:
   - `GET /health`
   - `GET /auth/status`
5. If bootstrap is required, create the first admin key through `POST /auth/bootstrap`.
6. Frontend stores the returned API key and loads protected data.

## 2. Overview workflow

1. Frontend loads:
   - `GET /agents`
   - `GET /models`
   - `GET /executions`
   - `GET /tracker/analytics`
   - `GET /diagnostics/reports/latest`
2. User submits a task through `POST /execute`.
3. Backend orchestrator selects an agent through internal scoring APIs.
4. Selected agent executes through internal execution APIs.
5. Execution, metrics, and logs are stored in PostgreSQL.
6. Frontend refreshes recent execution history.

## 3. Resume lab workflow

1. User uploads a resume file through `POST /resume/parse`.
2. Backend parses the file locally using `pypdf`, `python-docx`, or plain text decoding.
3. Frontend sends parsed text and optional JD text to `POST /resume/analyze`.
4. Backend computes:
   - ATS keywords
   - strengths
   - gaps
   - match score
   - suggested roles
   - LLM summary via local LLaMA, Azure OpenAI, or fallback
5. Analysis is persisted into `resume_analyses`.
6. User can ask follow-up questions through `POST /resume/chat`.

## 4. Job discovery workflow

1. User either:
   - pastes raw JD text, or
   - submits a trusted portal URL to `POST /job/extract`
2. Backend accepts only allowlisted portal hosts or manual text.
3. Frontend can then generate trusted source search links via `POST /job/search`.
4. Job query metadata is stored in `career_queries`.
5. Search results are stored in `job_search_results`.

## 5. Template studio workflow

1. Frontend loads `GET /resume/templates`.
2. User submits a new design brief through `POST /resume/templates/design`.
3. Backend generates:
   - recommended sections
   - design tokens
   - a Figma-ready creative brief
   - markdown preview text
4. Template records are stored in `resume_templates`.
5. Frontend refreshes the template catalog.

## 6. Chatbot workflow

1. User asks a general resume or career question via `POST /chat` or `POST /resume/chat`.
2. Chat context can include:
   - `resume_text`
   - `jd_text`
   - `session_id`
3. The chatbot uses Ollama first, Azure fallback second.
4. Session history is tracked in the in-memory `ChatStore`.

## 7. Local model workflow

### `llama-cpp-python`

1. Configure one or more `LLAMA_*_MODEL_PATH` variables.
2. Backend exposes local profiles through `GET /models`.
3. `CareerService` prefers local profiles for resume, JD, and template workloads.

### Ollama

1. Start `ollama serve`.
2. Pull a model such as `ollama pull llama3`.
3. Backend health for local inference is visible through `GET /ollama/status`.
4. Ollama-backed agents become effective when the local runtime is reachable.

## 8. Validation workflow

Recommended command sequence:

1. `./backend/venv/bin/python -m py_compile backend/*.py agents/*.py shared/*.py tests/*.py`
2. `cd frontend && npm run lint`
3. `cd frontend && npm run build`
4. `./backend/venv/bin/pytest tests/test_api.py -q`
5. `./backend/venv/bin/pytest tests/test_auth.py tests/test_storage.py tests/test_agents.py tests/test_workflow.py tests/test_orchestrator.py tests/test_diagnostics.py -q`
6. `./backend/venv/bin/pytest tests/test_postgres_integration.py -q`

PostgreSQL integration tests now skip cleanly when the configured `DATABASE_URL` is not reachable.

## 9. Production note

The current system of record is PostgreSQL for:

- auth
- logs
- metrics
- agent registry
- workflows
- execution history
- resume analyses
- template designs
- job query records
