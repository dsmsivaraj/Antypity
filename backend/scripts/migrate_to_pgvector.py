"""Migrate local fallback embeddings into PostgreSQL pgvector.

Usage:
  DATABASE_URL=... PYTHONPATH=. ./backend/venv/bin/python backend/scripts/migrate_to_pgvector.py
"""
from __future__ import annotations

import sys

from backend.config import get_settings
from backend.database import PostgreSQLDatabaseClient
from backend.embeddings_service import EmbeddingService


def main() -> int:
    settings = get_settings()
    if not settings.postgres_enabled:
        print("DATABASE_URL/POSTGRES_DSN is not configured.")
        return 1

    db = PostgreSQLDatabaseClient(settings)
    db.connect()
    if not db.has_pgvector():
        print("pgvector is not enabled in the target database.")
        return 1

    service = EmbeddingService(database_client=db)
    migrated = service.migrate_local_embeddings()
    print(f"Migrated {migrated} local embedding rows into PostgreSQL.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
