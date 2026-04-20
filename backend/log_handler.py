from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from .database import PostgreSQLDatabaseClient

# Loggers that write to the DB — exclude them to prevent recursion.
_EXCLUDED_PREFIXES = ("backend.database", "sqlalchemy")


class _NoRecurse(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not any(record.name.startswith(p) for p in _EXCLUDED_PREFIXES)


class PostgreSQLLogHandler(logging.Handler):
    """Writes structured log records to the execution_logs PostgreSQL table."""

    def __init__(self, db_client: PostgreSQLDatabaseClient, level: int = logging.INFO) -> None:
        super().__init__(level)
        self._db = db_client
        self.addFilter(_NoRecurse())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            execution_id: Optional[str] = getattr(record, "execution_id", None)
            agent_name: Optional[str] = getattr(record, "agent_name", None)
            extra: Optional[Dict[str, Any]] = getattr(record, "extra_data", None)

            self._db.save_log(
                level=record.levelname,
                logger=record.name,
                message=self.format(record),
                execution_id=execution_id,
                agent_name=agent_name,
                extra=extra,
            )
        except Exception:
            self.handleError(record)


def setup_logging(db_client: PostgreSQLDatabaseClient) -> None:
    """Configure application-wide logging: console + optional PostgreSQL sink."""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Prevent duplicate handlers when called more than once (e.g. test reloads).
    existing_types = {type(h) for h in root.handlers}

    if logging.StreamHandler not in existing_types:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    if db_client.is_configured and PostgreSQLLogHandler not in existing_types:
        pg_handler = PostgreSQLLogHandler(db_client)
        pg_handler.setFormatter(formatter)
        root.addHandler(pg_handler)

    # Silence SQLAlchemy engine noise unless debug mode wants it.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
