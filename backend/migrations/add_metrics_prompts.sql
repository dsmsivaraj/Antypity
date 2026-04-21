-- Add retrieval metrics and prompts registry tables

CREATE TABLE IF NOT EXISTS retrieval_metrics (
    id SERIAL PRIMARY KEY,
    query_text TEXT NOT NULL,
    top_k INT NOT NULL,
    result_count INT NOT NULL,
    avg_score FLOAT,
    latency_ms FLOAT,
    used_faiss BOOLEAN DEFAULT false,
    empty_context BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE TABLE IF NOT EXISTS prompt_registry (
    id SERIAL PRIMARY KEY,
    prompt_name TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    meta JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_retrieval_metrics_created_at ON retrieval_metrics(created_at);
CREATE INDEX IF NOT EXISTS idx_prompt_registry_name ON prompt_registry(prompt_name);
