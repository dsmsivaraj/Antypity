from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from .database import PostgreSQLDatabaseClient

_EXCLUDED_PREFIXES = ("backend.database", "sqlalchemy")

# Resolved relative to the project root (two levels up from this file).
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = _PROJECT_ROOT / os.getenv("LOG_DIR", "logs")
LOG_FILE = LOG_DIR / "app.log"
_LOG_MAX_BYTES = 10 * 1024 * 1024  # 10 MB per file
_LOG_BACKUP_COUNT = 5


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
    """Configure application-wide logging: console + rotating file + optional PostgreSQL sink."""
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Prevent duplicate handlers on multiple calls (e.g. test reloads).
    existing_types = {type(h) for h in root.handlers}

    if logging.StreamHandler not in existing_types:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        root.addHandler(console)

    if RotatingFileHandler not in existing_types:
        try:
            LOG_DIR.mkdir(parents=True, exist_ok=True)
            file_handler = RotatingFileHandler(
                LOG_FILE,
                maxBytes=_LOG_MAX_BYTES,
                backupCount=_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
        except OSError as exc:
            logging.getLogger(__name__).warning(
                "Could not create log file at %s: %s — file logging disabled.", LOG_FILE, exc
            )

    if db_client.is_configured and PostgreSQLLogHandler not in existing_types:
        pg_handler = PostgreSQLLogHandler(db_client)
        pg_handler.setFormatter(formatter)
        root.addHandler(pg_handler)

    # Silence SQLAlchemy engine noise unless debug mode wants it.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
