-- pgvector migration SQL
-- Run this on your Postgres instance that has the pgvector extension installed.
-- Example:
--   psql -d actypity -f backend/migrations/pgvector_migration.sql

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS resume_embeddings (
    id SERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    section_id TEXT NOT NULL,
    excerpt TEXT,
    embedding vector(384), -- adjust dimensionality to the encoder used (all-MiniLM-L6-v2 -> 384)
    score FLOAT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_resume_embeddings_embedding ON resume_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Note: Populate the table using the migration script backend/scripts/migrate_to_pgvector.py
