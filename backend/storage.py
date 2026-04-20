from __future__ import annotations

import json
from abc import ABC, abstractmethod
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from .config import Settings
from .database import PostgreSQLDatabaseClient


ExecutionRecord = Dict[str, Any]


class ExecutionStore(ABC):
    @abstractmethod
    def save(self, record: ExecutionRecord) -> ExecutionRecord:
        raise NotImplementedError

    @abstractmethod
    def list_recent(self, limit: int = 20) -> List[ExecutionRecord]:
        raise NotImplementedError


class JsonExecutionStore(ExecutionStore):
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def save(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock:
            records = self._load_unlocked()
            records.append(record)
            self.path.write_text(json.dumps(records, indent=2), encoding="utf-8")
        return record

    def list_recent(self, limit: int = 20) -> List[ExecutionRecord]:
        with self._lock:
            records = self._load_unlocked()
        return list(reversed(records[-limit:]))

    def _load_unlocked(self) -> List[ExecutionRecord]:
        if not self.path.exists():
            return []
        raw = self.path.read_text(encoding="utf-8").strip()
        if not raw:
            return []
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        return data if isinstance(data, list) else []


class InMemoryExecutionStore(ExecutionStore):
    def __init__(self):
        self._records: List[ExecutionRecord] = []
        self._lock = Lock()

    def save(self, record: ExecutionRecord) -> ExecutionRecord:
        with self._lock:
            self._records.append(record)
        return record

    def list_recent(self, limit: int = 20) -> List[ExecutionRecord]:
        with self._lock:
            return list(reversed(self._records[-limit:]))


class PostgreSQLExecutionStore(ExecutionStore):
    def __init__(self, client: PostgreSQLDatabaseClient):
        self.client = client

    def save(self, record: ExecutionRecord) -> ExecutionRecord:
        return self.client.save_execution(record)

    def list_recent(self, limit: int = 20) -> List[ExecutionRecord]:
        return self.client.list_executions(limit=limit)


def build_execution_store(
    settings: Settings,
    database_client: Optional[PostgreSQLDatabaseClient] = None,
) -> ExecutionStore:
    if settings.storage_backend == "memory":
        return InMemoryExecutionStore()
    if settings.storage_backend == "postgres":
        return PostgreSQLExecutionStore(database_client or PostgreSQLDatabaseClient(settings))
    return JsonExecutionStore(settings.storage_path)
