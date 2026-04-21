# Antypity

Antypity is a production-ready career intelligence and agent orchestration platform built with a FastAPI backend and a React + Bootstrap frontend.

[![CI](https://github.com/dsmsivaraj/Antypity/actions/workflows/ci.yml/badge.svg)](https://github.com/dsmsivaraj/Antypity/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

## What the application does

- Multi-agent and multi-model orchestration through internal platform APIs
- PostgreSQL-backed persistence for executions, logs, metrics, auth, agent registry, workflows, and career artifacts
- Local resume parsing for `pdf`, `docx`, and `txt`
- Resume analysis against a job description using local LLaMA/Ollama when available, with Azure OpenAI and deterministic fallbacks
- Resume chatbot for querying resume strength, ATS gaps, and JD fit
- Trusted job source discovery for LinkedIn, Indeed, Glassdoor, Wellfound, Naukri, Dice, and ZipRecruiter
- Resume template generation with Figma-ready creative briefs and a built-in template catalog

## Main product surfaces

- `Overview` — orchestration console, execution history, diagnostics, self-healing status
- `Resume Lab` — upload, parse, analyze, and chat about a resume
- `Job Discovery` — normalize a JD and generate trusted job portal search links
- `Template Studio` — browse templates and generate new resume template briefs for Figma

## Local runtime contract

- Backend: `http://localhost:9500`
- Frontend dev: `http://localhost:5173`
- Frontend build preview: `http://localhost:4173`
- Local Ollama default: `http://localhost:11434`

## Environment

### Core

```env
APP_STORAGE_BACKEND=postgres
DATABASE_URL=postgresql+psycopg:///actypity?host=/tmp&user=<your_local_user>
API_PORT=9500
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
BOOTSTRAP_ADMIN_TOKEN=change-me
INTERNAL_API_TOKEN=change-me
```

### Optional Azure OpenAI

```env
AZURE_OPENAI_API_KEY=
AZURE_OPENAI_ENDPOINT=
AZURE_OPENAI_DEPLOYMENT=
AZURE_OPENAI_PLANNER_DEPLOYMENT=
AZURE_OPENAI_REVIEWER_DEPLOYMENT=
```

### Optional local LLaMA via `llama-cpp-python`

```env
LLAMA_MODEL_PATH=/absolute/path/to/model.gguf
LLAMA_RESUME_MODEL_PATH=/absolute/path/to/resume-model.gguf
LLAMA_JOB_MODEL_PATH=/absolute/path/to/job-model.gguf
LLAMA_TEMPLATE_MODEL_PATH=/absolute/path/to/template-model.gguf
LLAMA_N_CTX=4096
LLAMA_TEMPERATURE=0.2
```

### Optional Ollama

```env
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3
```

### Optional Figma

```env
FIGMA_ACCESS_TOKEN=
FIGMA_TEAM_ID=
FIGMA_FILE_KEY=
```

## Run the application

### 1. Backend

```bash
./activate_and_update_venv.sh
./run_backend.sh
```

If you want local `llama-cpp-python` support too:

```bash
source backend/venv/bin/activate
pip install -r backend/requirements-llama.txt
```

If you want Ollama-backed local agents:

```bash
ollama serve
ollama pull llama3
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Test the application

### Frontend

```bash
cd frontend
npm run lint
npm run build
```

### Backend

```bash
./backend/venv/bin/python -m py_compile backend/*.py agents/*.py shared/*.py tests/*.py
./backend/venv/bin/pytest tests/test_api.py -q
./backend/venv/bin/pytest tests/test_auth.py tests/test_storage.py tests/test_agents.py tests/test_workflow.py tests/test_orchestrator.py tests/test_diagnostics.py -q
./backend/venv/bin/pytest tests/test_postgres_integration.py -q
```

Note:
- `tests/test_postgres_integration.py` now skips automatically when `DATABASE_URL` is not reachable from the current environment.

## Key backend endpoints

- `GET /health`
- `GET /ready`
- `GET /auth/status`
- `POST /auth/bootstrap`
- `GET /agents`
- `GET /models`
- `POST /execute`
- `GET /executions`
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
- `GET /metrics`
- `GET /logs`

## Engineering references

- [Application Knowledge](./APPLICATION_KNOWLEDGE.md)
- [Application Skills](./APPLICATION_SKILLS.md)
- [Application Workflow](./APPLICATION_WORKFLOW.md)
- [Validation Report](./VALIDATION_REPORT.md)
- [LLaMA Integration Notes](./docs/llama_integration.md)
