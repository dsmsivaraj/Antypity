from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
    create_engine,
    insert,
    select,
    text,
    update,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool

from .config import Settings


@dataclass(frozen=True)
class DatabaseStatus:
    connected: bool
    backend: str
    detail: str


class PostgreSQLDatabaseClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._engine: Optional[Engine] = None
        self._metadata = MetaData()
        self._define_tables()

    # ── Table definitions ────────────────────────────────────────────────────

    def _define_tables(self) -> None:
        self.executions = Table(
            "executions",
            self._metadata,
            _str("execution_id", primary_key=True),
            _str("agent_name", nullable=False),
            _str("status", nullable=False),
            Column("output", String, nullable=False),
            Column("used_llm", Boolean, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("context", JSON, nullable=False),
        )

        self.api_keys = Table(
            "api_keys",
            self._metadata,
            _str("id", primary_key=True),
            _str("name", nullable=False),
            _str("key_hash", nullable=False),
            _str("role", nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("is_active", Boolean, nullable=False),
            UniqueConstraint("key_hash", name="uq_api_keys_key_hash"),
        )

        self.agent_registry = Table(
            "agent_registry",
            self._metadata,
            _str("name", primary_key=True),
            _str("description", nullable=False),
            Column("capabilities", JSON, nullable=False),
            Column("supports_tools", Boolean, nullable=False),
            _str("agent_class", nullable=False),
            Column("is_active", Boolean, nullable=False),
            Column("registered_at", DateTime(timezone=True), nullable=False),
            Column("last_seen_at", DateTime(timezone=True), nullable=False),
        )

        self.execution_logs = Table(
            "execution_logs",
            self._metadata,
            _str("id", primary_key=True),
            Column("execution_id", String, nullable=True),
            _str("level", nullable=False),
            _str("logger", nullable=False),
            Column("message", String, nullable=False),
            Column("agent_name", String, nullable=True),
            Column("extra", JSON, nullable=True),
            Column("timestamp", DateTime(timezone=True), nullable=False),
        )

        self.agent_metrics = Table(
            "agent_metrics",
            self._metadata,
            _str("agent_name", primary_key=True),
            Column("total_executions", Integer, nullable=False),
            Column("llm_executions", Integer, nullable=False),
            Column("failed_executions", Integer, nullable=False),
            Column("last_executed_at", DateTime(timezone=True), nullable=True),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )

        self.workflow_definitions = Table(
            "workflow_definitions",
            self._metadata,
            _str("id", primary_key=True),
            _str("name", nullable=False),
            Column("description", String, nullable=True),
            Column("steps", JSON, nullable=False),
            Column("created_by", String, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint("name", name="uq_workflow_definitions_name"),
        )

        self.workflow_executions = Table(
            "workflow_executions",
            self._metadata,
            _str("id", primary_key=True),
            _str("workflow_id", nullable=False),
            _str("status", nullable=False),
            Column("current_step", Integer, nullable=False),
            Column("total_steps", Integer, nullable=False),
            Column("results", JSON, nullable=False),
            Column("error", String, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("completed_at", DateTime(timezone=True), nullable=True),
        )

    # ── Connection management ────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        return self.settings.postgres_enabled

    def connect(self) -> None:
        if self._engine is not None:
            return
        if not self.is_configured:
            raise RuntimeError("PostgreSQL is not configured.")
        self._engine = create_engine(
            self.settings.resolved_postgres_dsn,
            poolclass=QueuePool,
            pool_size=self.settings.postgres_pool_size,
            max_overflow=self.settings.postgres_max_overflow,
            pool_pre_ping=True,
            echo=self.settings.postgres_echo,
            future=True,
        )
        self._metadata.create_all(self._engine)

    @property
    def engine(self) -> Engine:
        self.connect()
        assert self._engine is not None
        return self._engine

    def get_status(self) -> DatabaseStatus:
        if not self.is_configured:
            return DatabaseStatus(connected=False, backend="postgres", detail="PostgreSQL not configured.")
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return DatabaseStatus(connected=True, backend="postgres", detail="ok")
        except Exception as exc:
            return DatabaseStatus(connected=False, backend="postgres", detail=str(exc))

    # ── Executions ───────────────────────────────────────────────────────────

    def save_execution(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(item)
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        with self.engine.begin() as conn:
            conn.execute(insert(self.executions).values(**payload))
        return item

    def list_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = (
            select(self.executions)
            .order_by(self.executions.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    # ── API Keys ─────────────────────────────────────────────────────────────

    def create_api_key(self, name: str, role: str, key_hash: str) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "id": str(uuid4()),
            "name": name,
            "key_hash": key_hash,
            "role": role,
            "created_at": datetime.now(timezone.utc),
            "is_active": True,
        }
        with self.engine.begin() as conn:
            conn.execute(insert(self.api_keys).values(**record))
        return _serialize(record)

    def get_api_key_by_hash(self, key_hash: str) -> Optional[Dict[str, Any]]:
        query = select(self.api_keys).where(
            self.api_keys.c.key_hash == key_hash,
            self.api_keys.c.is_active == True,  # noqa: E712
        )
        with self.engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _serialize(dict(row)) if row else None

    def list_api_keys(self) -> List[Dict[str, Any]]:
        query = select(
            self.api_keys.c.id,
            self.api_keys.c.name,
            self.api_keys.c.role,
            self.api_keys.c.created_at,
            self.api_keys.c.is_active,
        ).order_by(self.api_keys.c.created_at.desc())
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    def deactivate_api_key(self, key_id: str) -> bool:
        stmt = (
            update(self.api_keys)
            .where(self.api_keys.c.id == key_id)
            .values(is_active=False)
        )
        with self.engine.begin() as conn:
            result = conn.execute(stmt)
        return result.rowcount > 0

    def has_any_api_key(self) -> bool:
        query = (
            select(self.api_keys.c.id)
            .where(self.api_keys.c.is_active == True)  # noqa: E712
            .limit(1)
        )
        with self.engine.connect() as conn:
            return conn.execute(query).first() is not None

    # ── Agent Registry ───────────────────────────────────────────────────────

    def upsert_agent_registry(
        self,
        name: str,
        description: str,
        capabilities: List[str],
        supports_tools: bool,
        agent_class: str,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        record: Dict[str, Any] = {
            "name": name,
            "description": description,
            "capabilities": capabilities,
            "supports_tools": supports_tools,
            "agent_class": agent_class,
            "is_active": True,
            "registered_at": now,
            "last_seen_at": now,
        }
        stmt = pg_insert(self.agent_registry).values(**record).on_conflict_do_update(
            index_elements=["name"],
            set_={
                "description": description,
                "capabilities": capabilities,
                "supports_tools": supports_tools,
                "is_active": True,
                "last_seen_at": now,
            },
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)
        return _serialize(record)

    def list_agent_registry(self) -> List[Dict[str, Any]]:
        query = (
            select(self.agent_registry)
            .where(self.agent_registry.c.is_active == True)  # noqa: E712
            .order_by(self.agent_registry.c.name)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    # ── Execution Logs ───────────────────────────────────────────────────────

    def save_log(
        self,
        level: str,
        logger: str,
        message: str,
        execution_id: Optional[str] = None,
        agent_name: Optional[str] = None,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        record = {
            "id": str(uuid4()),
            "execution_id": execution_id,
            "level": level,
            "logger": logger,
            "message": message,
            "agent_name": agent_name,
            "extra": extra,
            "timestamp": datetime.now(timezone.utc),
        }
        with self.engine.begin() as conn:
            conn.execute(insert(self.execution_logs).values(**record))

    def list_logs(
        self,
        limit: int = 50,
        level: Optional[str] = None,
        execution_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        query = select(self.execution_logs)
        if level:
            query = query.where(self.execution_logs.c.level == level.upper())
        if execution_id:
            query = query.where(self.execution_logs.c.execution_id == execution_id)
        query = query.order_by(self.execution_logs.c.timestamp.desc()).limit(min(limit, 500))
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    # ── Agent Metrics ────────────────────────────────────────────────────────

    def record_metric(self, agent_name: str, used_llm: bool, failed: bool) -> None:
        now = datetime.now(timezone.utc)
        stmt = pg_insert(self.agent_metrics).values(
            agent_name=agent_name,
            total_executions=1,
            llm_executions=1 if used_llm else 0,
            failed_executions=1 if failed else 0,
            last_executed_at=now,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=["agent_name"],
            set_={
                "total_executions": self.agent_metrics.c.total_executions + 1,
                "llm_executions": self.agent_metrics.c.llm_executions + (1 if used_llm else 0),
                "failed_executions": self.agent_metrics.c.failed_executions + (1 if failed else 0),
                "last_executed_at": now,
                "updated_at": now,
            },
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def list_metrics(self) -> List[Dict[str, Any]]:
        query = select(self.agent_metrics).order_by(self.agent_metrics.c.agent_name)
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    # ── Workflow Definitions ─────────────────────────────────────────────────

    def save_workflow_definition(
        self,
        name: str,
        description: str,
        steps: List[Dict[str, Any]],
        created_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "id": str(uuid4()),
            "name": name,
            "description": description,
            "steps": steps,
            "created_by": created_by,
            "created_at": datetime.now(timezone.utc),
        }
        with self.engine.begin() as conn:
            conn.execute(insert(self.workflow_definitions).values(**record))
        return _serialize(record)

    def list_workflow_definitions(self) -> List[Dict[str, Any]]:
        query = select(self.workflow_definitions).order_by(
            self.workflow_definitions.c.created_at.desc()
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    def get_workflow_definition(self, workflow_id: str) -> Optional[Dict[str, Any]]:
        query = select(self.workflow_definitions).where(
            self.workflow_definitions.c.id == workflow_id
        )
        with self.engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _serialize(dict(row)) if row else None

    # ── Workflow Executions ──────────────────────────────────────────────────

    def create_workflow_execution(
        self, workflow_id: str, total_steps: int
    ) -> Dict[str, Any]:
        record: Dict[str, Any] = {
            "id": str(uuid4()),
            "workflow_id": workflow_id,
            "status": "running",
            "current_step": 0,
            "total_steps": total_steps,
            "results": [],
            "error": None,
            "created_at": datetime.now(timezone.utc),
            "completed_at": None,
        }
        with self.engine.begin() as conn:
            conn.execute(insert(self.workflow_executions).values(**record))
        return _serialize(record)

    def update_workflow_execution(self, execution_id: str, **kwargs: Any) -> None:
        if kwargs.get("status") in ("completed", "failed") and "completed_at" not in kwargs:
            kwargs["completed_at"] = datetime.now(timezone.utc)
        stmt = (
            update(self.workflow_executions)
            .where(self.workflow_executions.c.id == execution_id)
            .values(**kwargs)
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def list_workflow_executions(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = (
            select(self.workflow_executions)
            .order_by(self.workflow_executions.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    def get_workflow_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        query = select(self.workflow_executions).where(
            self.workflow_executions.c.id == execution_id
        )
        with self.engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _serialize(dict(row)) if row else None

    def reset_all(self) -> None:
        with self.engine.begin() as conn:
            for table in reversed(self._metadata.sorted_tables):
                conn.execute(table.delete())


# ── Helpers ──────────────────────────────────────────────────────────────────

def _str(name: str, **kwargs: Any) -> Column:
    return Column(name, String, **kwargs)


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in row.items()
    }
