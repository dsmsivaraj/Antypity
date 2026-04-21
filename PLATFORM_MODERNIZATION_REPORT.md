# Platform Modernization Report

## Scope

This pass reviewed the active Actypity application path as a production-grade job search AI platform, with emphasis on:

- platform observability
- retrieval and grounding quality
- LLM safety and drift risk
- frontend operator visibility
- realistic next-step architecture for hybrid RAG and future tuning

## What was fixed

1. Corrected `/platform/insights` so `self_healing_running` reflects the self-healing controller state rather than the diagnostics scheduler state.
2. Added platform-insights loading to the frontend overview and surfaced platform posture metrics:
   - registered agents
   - model profiles
   - retrieval document count
   - self-healing state
3. Updated application knowledge and skills to reflect:
   - the current retrieval stack
   - current observability surface
   - known production gaps
   - the recommended roadmap for hallucination reduction, drift monitoring, hybrid RAG, and future fine-tuning

## Current gaps

1. Retrieval is still local-file based.
`backend/embeddings_service.py` uses FAISS when available, but metadata and fallback indexing remain local. This is not yet multi-user safe or operationally robust.

2. Grounding is best-effort, not enforced.
Resume chat can pull retrieved context, but the product does not yet require citations or evidence-backed outputs across resume chat, JD extraction, recruiter contacts, and cover letters.

3. Metrics are operational, not epistemic.
The platform tracks execution counts and LLM usage, but not retrieval hit-rate, citation coverage, fallback rate, or answer faithfulness.

4. Prompt logic is not versioned.
Prompt behavior currently lives in code without a first-class registry, experiment metadata, or rollback mechanism.

5. Drift detection is missing.
There is no automated monitoring for job-source freshness, ATS-scoring drift, recruiter-contact confidence drift, or prompt-output regressions.

## Recommended implementation sequence

1. Add evidence-first response contracts.
Extend high-impact APIs to return confidence, provenance, and citations.

2. Add quality metrics in PostgreSQL.
Track retrieval hit-rate, empty-context rate, citation coverage, fallback usage, and latency percentiles.

3. Add prompt versioning.
Persist prompt version IDs per execution and compare offline eval results before rollout.

4. Move retrieval to hybrid RAG.
Keep PostgreSQL as source of record and add `pgvector` plus lexical retrieval and re-ranking.

5. Add verification on high-risk outputs.
Introduce critic or rules-based verification for cover letters, recruiter contacts, and tailored applications.

6. Add evaluation datasets before fine-tuning.
Collect resume/JD examples, preferred rewrites, verified recruiter contacts, and outcome-linked job-fit judgments.

7. Consider tuning only after retrieval and eval maturity.
Use tuning for style and ranking improvements, not as a substitute for grounding.

## Hybrid RAG target

- PostgreSQL for records and analytics
- `pgvector` for embeddings
- lexical search for exact skills, roles, companies, and locations
- vector retrieval for semantic recall
- re-ranking for final chunk selection
- provenance returned to the UI for trust and debugging

## Run and test commands

Backend:

```bash
./activate_and_update_venv.sh
./run_backend.sh
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Validation:

```bash
PYTHONPATH=. ./backend/venv/bin/python -m py_compile backend/*.py agents/*.py tests/*.py
PYTHONPATH=. ./backend/venv/bin/pytest tests/test_api.py -q
cd frontend && npm run lint && npm run build
```
