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
            Column("model_profile", String, nullable=True),
            Column("provider", String, nullable=True),
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

        self.diagnostic_runs = Table(
            "diagnostic_runs",
            self._metadata,
            _str("id", primary_key=True),
            _str("status", nullable=False),
            Column("health", JSON, nullable=True),
            Column("tests", JSON, nullable=True),
            Column("issues", JSON, nullable=False),
            Column("summary", String, nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("completed_at", DateTime(timezone=True), nullable=True),
        )

        self.users = Table(
            "users",
            self._metadata,
            _str("id", primary_key=True),
            _str("email", nullable=False),
            _str("full_name", nullable=True),
            _str("social_provider", nullable=True),  # google, facebook, etc.
            _str("social_id", nullable=True),
            _str("role", nullable=False),  # admin, recruiter, applicant
            _str("status", nullable=False),  # pending, approved, active, disabled
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint("email", name="uq_users_email"),
        )

        self.user_sessions = Table(
            "user_sessions",
            self._metadata,
            _str("id", primary_key=True),
            _str("user_id", nullable=False),
            _str("token", nullable=False),
            Column("expires_at", DateTime(timezone=True), nullable=False),
            Column("created_at", DateTime(timezone=True), nullable=False),
            UniqueConstraint("token", name="uq_user_sessions_token"),
        )

        self.user_profiles = Table(
            "user_profiles",
            self._metadata,
            _str("user_id", primary_key=True),
            Column("resume_data", JSON, nullable=True),
            Column("onboarding_metadata", JSON, nullable=True),
            Column("preferences", JSON, nullable=True),
            Column("embedding", JSON, nullable=True), # Store as JSON/List for now, or use pgvector types
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )

        self.job_search_results = Table(
            "job_search_results",
            self._metadata,
            _str("id", primary_key=True),
            _str("title", nullable=False),
            _str("company", nullable=False),
            _str("description", nullable=False),
            _str("url", nullable=False),
            Column("source", String, nullable=True),
            Column("location", String, nullable=True),
            Column("summary", String, nullable=True),
            Column("embedding", JSON, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )

        self.resume_analyses = Table(
            "resume_analyses",
            self._metadata,
            _str("id", primary_key=True),
            _str("title", nullable=False),
            Column("source_filename", String, nullable=True),
            Column("resume_text", String, nullable=False),
            Column("jd_text", String, nullable=True),
            Column("summary", String, nullable=False),
            Column("match_score", Integer, nullable=False),
            Column("suggestions", JSON, nullable=False),
            Column("ats_keywords", JSON, nullable=False),
            Column("strengths", JSON, nullable=False),
            Column("gaps", JSON, nullable=False),
            Column("recommended_roles", JSON, nullable=False),
            Column("model_profile", String, nullable=True),
            Column("used_llm", Boolean, nullable=True),
            Column("provider", String, nullable=True),
            Column("parsed_fields", JSON, nullable=True),
            Column("created_by", String, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )

        self.resume_templates = Table(
            "resume_templates",
            self._metadata,
            _str("id", primary_key=True),
            _str("name", nullable=False),
            _str("target_role", nullable=False),
            _str("style", nullable=False),
            Column("notes", String, nullable=True),
            Column("figma_prompt", String, nullable=False),
            Column("sections", JSON, nullable=False),
            Column("design_tokens", JSON, nullable=False),
            Column("preview_markdown", String, nullable=False),
            Column("model_profile", String, nullable=True),
            Column("created_by", String, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )

        self.career_queries = Table(
            "career_queries",
            self._metadata,
            _str("id", primary_key=True),
            _str("query_type", nullable=False),
            Column("query_text", String, nullable=False),
            Column("sources", JSON, nullable=False),
            Column("result_count", Integer, nullable=False),
            Column("metadata", JSON, nullable=True),
            Column("created_by", String, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
        )

        self.response_quality_metrics = Table(
            "response_quality_metrics",
            self._metadata,
            Column("id", Integer, primary_key=True, autoincrement=True),
            _str("response_type", nullable=False),
            Column("grounding_score", Integer, nullable=False),
            Column("citation_count", Integer, nullable=False),
            _str("confidence", nullable=False),
            Column("drift_flag", Boolean, nullable=False),
            Column("metadata", JSON, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
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
        # Enable pgvector if available on this PostgreSQL instance.
        try:
            with self._engine.begin() as conn:
                conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        self._apply_migrations()

    def _apply_migrations(self) -> None:
        """Add columns that were introduced after the initial table creation."""
        migrations = [
            "ALTER TABLE job_search_results ADD COLUMN IF NOT EXISTS source VARCHAR",
            "ALTER TABLE job_search_results ADD COLUMN IF NOT EXISTS location VARCHAR",
            "ALTER TABLE job_search_results ADD COLUMN IF NOT EXISTS summary VARCHAR",
            "ALTER TABLE resume_analyses ADD COLUMN IF NOT EXISTS model_profile VARCHAR",
            "ALTER TABLE resume_analyses ADD COLUMN IF NOT EXISTS used_llm BOOLEAN DEFAULT false",
            "ALTER TABLE resume_analyses ADD COLUMN IF NOT EXISTS provider VARCHAR",
            "ALTER TABLE resume_analyses ADD COLUMN IF NOT EXISTS source_filename VARCHAR",
            "ALTER TABLE resume_analyses ADD COLUMN IF NOT EXISTS parsed_fields JSONB",
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_users_social ON users(social_provider, social_id) WHERE social_provider IS NOT NULL AND social_id IS NOT NULL",
            """
            CREATE TABLE IF NOT EXISTS retrieval_metrics (
                id BIGSERIAL PRIMARY KEY,
                query_text TEXT NOT NULL,
                top_k INTEGER NOT NULL,
                result_count INTEGER NOT NULL,
                avg_score DOUBLE PRECISION NOT NULL,
                latency_ms DOUBLE PRECISION NOT NULL,
                used_faiss BOOLEAN NOT NULL DEFAULT false,
                empty_context BOOLEAN NOT NULL DEFAULT false,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_retrieval_metrics_created_at ON retrieval_metrics(created_at)",
            """
            CREATE TABLE IF NOT EXISTS response_quality_metrics (
                id BIGSERIAL PRIMARY KEY,
                response_type TEXT NOT NULL,
                grounding_score INTEGER NOT NULL,
                citation_count INTEGER NOT NULL,
                confidence TEXT NOT NULL,
                drift_flag BOOLEAN NOT NULL DEFAULT false,
                metadata JSON,
                created_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_response_quality_metrics_created_at ON response_quality_metrics(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_response_quality_metrics_response_type ON response_quality_metrics(response_type)",
        ]
        try:
            with self._engine.begin() as conn:
                for stmt in migrations:
                    conn.execute(text(stmt))
                if self._pgvector_enabled(conn):
                    conn.execute(
                        text(
                            """
                            CREATE TABLE IF NOT EXISTS resume_embeddings (
                                id BIGSERIAL PRIMARY KEY,
                                doc_id TEXT NOT NULL,
                                section_id TEXT NOT NULL,
                                excerpt TEXT,
                                embedding vector(384),
                                score DOUBLE PRECISION NOT NULL DEFAULT 0,
                                created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                                UNIQUE (doc_id, section_id)
                            )
                            """
                        )
                    )
                    conn.execute(
                        text(
                            "CREATE INDEX IF NOT EXISTS idx_resume_embeddings_doc_id ON resume_embeddings(doc_id)"
                        )
                    )
        except Exception:
            pass  # non-PostgreSQL backends or permission issues — safe to skip

    def _pgvector_enabled(self, conn) -> bool:
        return bool(
            conn.execute(
                text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")
            ).scalar()
        )

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

    def has_pgvector(self) -> bool:
        if not self.is_configured:
            return False
        try:
            with self.engine.connect() as conn:
                return self._pgvector_enabled(conn)
        except Exception:
            return False

    def count_resume_embeddings(self) -> int:
        if not self.has_pgvector():
            return 0
        with self.engine.connect() as conn:
            value = conn.execute(text("SELECT COUNT(*) FROM resume_embeddings")).scalar()
        return int(value or 0)

    def upsert_resume_embedding(
        self,
        *,
        doc_id: str,
        section_id: str,
        excerpt: str,
        embedding: List[float],
        score: float = 0.0,
    ) -> bool:
        if not self.has_pgvector():
            return False
        vector_literal = "[" + ",".join(f"{float(item):.8g}" for item in embedding) + "]"
        stmt = text(
            """
            INSERT INTO resume_embeddings (doc_id, section_id, excerpt, embedding, score)
            VALUES (:doc_id, :section_id, :excerpt, CAST(:embedding AS vector), :score)
            ON CONFLICT (doc_id, section_id)
            DO UPDATE SET
                excerpt = EXCLUDED.excerpt,
                embedding = EXCLUDED.embedding,
                score = EXCLUDED.score
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "doc_id": doc_id,
                    "section_id": section_id,
                    "excerpt": excerpt[:4000],
                    "embedding": vector_literal,
                    "score": float(score),
                },
            )
        return True

    def query_resume_embeddings(
        self,
        *,
        embedding: List[float],
        top_k: int = 5,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.has_pgvector():
            return []
        vector_literal = "[" + ",".join(f"{float(item):.8g}" for item in embedding) + "]"
        where_clause = "WHERE doc_id = :doc_id" if doc_id else ""
        stmt = text(
            f"""
            SELECT
                doc_id,
                section_id,
                excerpt AS text,
                1 - (embedding <=> CAST(:embedding AS vector)) AS score
            FROM resume_embeddings
            {where_clause}
            ORDER BY embedding <=> CAST(:embedding AS vector) ASC
            LIMIT :top_k
            """
        )
        params: Dict[str, Any] = {"embedding": vector_literal, "top_k": int(top_k)}
        if doc_id:
            params["doc_id"] = doc_id
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, params).mappings().all()
        return [_serialize(dict(row)) for row in rows]

    def record_retrieval_metric(
        self,
        *,
        query_text: str,
        top_k: int,
        result_count: int,
        avg_score: float,
        latency_ms: float,
        used_faiss: bool,
        empty_context: bool,
    ) -> None:
        stmt = text(
            """
            INSERT INTO retrieval_metrics
                (query_text, top_k, result_count, avg_score, latency_ms, used_faiss, empty_context)
            VALUES
                (:query_text, :top_k, :result_count, :avg_score, :latency_ms, :used_faiss, :empty_context)
            """
        )
        with self.engine.begin() as conn:
            conn.execute(
                stmt,
                {
                    "query_text": query_text[:4000],
                    "top_k": int(top_k),
                    "result_count": int(result_count),
                    "avg_score": float(avg_score),
                    "latency_ms": float(latency_ms),
                    "used_faiss": bool(used_faiss),
                    "empty_context": bool(empty_context),
                },
            )

    def get_retrieval_metrics_summary(self) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total_queries,
                        COALESCE(AVG(latency_ms), 0) AS avg_latency_ms,
                        COALESCE(AVG(avg_score), 0) AS avg_score,
                        COALESCE(AVG(CASE WHEN empty_context THEN 1.0 ELSE 0.0 END), 0) AS empty_context_rate,
                        COALESCE(AVG(CASE WHEN result_count > 0 THEN 1.0 ELSE 0.0 END), 0) AS hit_rate
                    FROM retrieval_metrics
                    """
                )
            ).mappings().first()
        if not row:
            return {
                "total_queries": 0,
                "avg_latency_ms": 0.0,
                "avg_score": 0.0,
                "empty_context_rate": 0.0,
                "hit_rate": 0.0,
            }
        result = dict(row)
        return {
            "total_queries": int(result.get("total_queries") or 0),
            "avg_latency_ms": float(result.get("avg_latency_ms") or 0.0),
            "avg_score": float(result.get("avg_score") or 0.0),
            "empty_context_rate": float(result.get("empty_context_rate") or 0.0),
            "hit_rate": float(result.get("hit_rate") or 0.0),
        }

    def record_response_quality_metric(
        self,
        *,
        response_type: str,
        grounding_score: int,
        citation_count: int,
        confidence: str,
        drift_flag: bool,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        stmt = insert(self.response_quality_metrics).values(
            response_type=response_type[:100],
            grounding_score=max(0, min(int(grounding_score), 100)),
            citation_count=max(0, int(citation_count)),
            confidence=(confidence or "medium")[:20],
            drift_flag=bool(drift_flag),
            metadata=metadata,
            created_at=datetime.now(timezone.utc),
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def get_response_quality_summary(self) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total_evaluations,
                        COALESCE(AVG(grounding_score), 0) AS avg_grounding_score,
                        COALESCE(AVG(citation_count), 0) AS avg_citation_count,
                        COALESCE(SUM(CASE WHEN drift_flag THEN 1 ELSE 0 END), 0) AS drift_alerts
                    FROM response_quality_metrics
                    """
                )
            ).mappings().first()
        if not row:
            return {
                "total_evaluations": 0,
                "avg_grounding_score": 0.0,
                "avg_citation_count": 0.0,
                "drift_alerts": 0,
            }
        result = dict(row)
        return {
            "total_evaluations": int(result.get("total_evaluations") or 0),
            "avg_grounding_score": float(result.get("avg_grounding_score") or 0.0),
            "avg_citation_count": float(result.get("avg_citation_count") or 0.0),
            "drift_alerts": int(result.get("drift_alerts") or 0),
        }

    def lexical_search_resume_embeddings(
        self,
        *,
        keywords: List[str],
        top_k: int = 5,
        doc_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        if not self.has_pgvector() or not keywords:
            return []
        clauses = []
        params: Dict[str, Any] = {"top_k": int(top_k)}
        for idx, keyword in enumerate(keywords):
            key = f"kw_{idx}"
            clauses.append(f"CASE WHEN excerpt ILIKE :{key} THEN 1 ELSE 0 END")
            params[key] = f"%{keyword}%"
        where_doc = "AND doc_id = :doc_id" if doc_id else ""
        if doc_id:
            params["doc_id"] = doc_id
        stmt = text(
            f"""
            SELECT
                doc_id,
                section_id,
                excerpt AS text,
                ({' + '.join(clauses)})::double precision AS score
            FROM resume_embeddings
            WHERE excerpt IS NOT NULL
            {where_doc}
            ORDER BY score DESC, created_at DESC
            LIMIT :top_k
            """
        )
        with self.engine.connect() as conn:
            rows = conn.execute(stmt, params).mappings().all()
        return [row for row in (_serialize(dict(r)) for r in rows) if float(row.get("score", 0.0)) > 0]

    # ── Executions ───────────────────────────────────────────────────────────

    def save_execution(self, item: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(item)
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        valid_columns = set(self.executions.c.keys())
        payload = {key: value for key, value in payload.items() if key in valid_columns}
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

    # ── Diagnostic Runs ──────────────────────────────────────────────────────

    def save_diagnostic_run(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record)
        for key in ("created_at", "completed_at"):
            if isinstance(payload.get(key), str):
                try:
                    payload[key] = datetime.fromisoformat(payload[key])
                except ValueError:
                    payload[key] = None
        valid_columns = set(self.diagnostic_runs.c.keys())
        payload = {k: v for k, v in payload.items() if k in valid_columns}
        with self.engine.begin() as conn:
            conn.execute(insert(self.diagnostic_runs).values(**payload))
        return record

    def list_diagnostic_runs(self, limit: int = 10) -> List[Dict[str, Any]]:
        query = (
            select(self.diagnostic_runs)
            .order_by(self.diagnostic_runs.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    def reset_all(self) -> None:
        self._metadata.drop_all(self.engine)
        self._metadata.create_all(self.engine)

    # ── Resume analyses ─────────────────────────────────────────────────────

    def save_resume_analysis(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record)
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        valid_columns = set(self.resume_analyses.c.keys())
        payload = {key: value for key, value in payload.items() if key in valid_columns}
        with self.engine.begin() as conn:
            conn.execute(insert(self.resume_analyses).values(**payload))
        return _serialize(payload)

    def list_resume_analyses(self, limit: int = 20) -> List[Dict[str, Any]]:
        query = (
            select(self.resume_analyses)
            .order_by(self.resume_analyses.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    # ── Resume templates ────────────────────────────────────────────────────

    def save_resume_template(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record)
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        valid_columns = set(self.resume_templates.c.keys())
        payload = {key: value for key, value in payload.items() if key in valid_columns}
        with self.engine.begin() as conn:
            conn.execute(insert(self.resume_templates).values(**payload))
        return _serialize(payload)

    def list_resume_templates(self, limit: int = 50) -> List[Dict[str, Any]]:
        query = (
            select(self.resume_templates)
            .order_by(self.resume_templates.c.created_at.desc())
            .limit(limit)
        )
        with self.engine.connect() as conn:
            rows = conn.execute(query).mappings().all()
        return [_serialize(dict(r)) for r in rows]

    # ── Career queries / analytics ──────────────────────────────────────────

    def save_career_query(self, record: Dict[str, Any]) -> Dict[str, Any]:
        payload = dict(record)
        if isinstance(payload.get("created_at"), str):
            payload["created_at"] = datetime.fromisoformat(payload["created_at"])
        valid_columns = set(self.career_queries.c.keys())
        payload = {key: value for key, value in payload.items() if key in valid_columns}
        with self.engine.begin() as conn:
            conn.execute(insert(self.career_queries).values(**payload))
        return _serialize(payload)

    def save_job_search_results(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        valid_columns = set(self.job_search_results.c.keys())
        payloads = []
        for record in records:
            payload = {key: value for key, value in record.items() if key in valid_columns}
            if isinstance(payload.get("created_at"), str):
                payload["created_at"] = datetime.fromisoformat(payload["created_at"])
            payloads.append(payload)
        with self.engine.begin() as conn:
            conn.execute(insert(self.job_search_results), payloads)

    # ── Users / profiles ────────────────────────────────────────────────────

    def upsert_user(
        self,
        *,
        email: str,
        full_name: str,
        social_provider: str,
        social_id: str,
        role: str = "applicant",
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        record: Dict[str, Any] = {
            "id": str(uuid4()),
            "email": email,
            "full_name": full_name,
            "social_provider": social_provider,
            "social_id": social_id,
            "role": role,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        }
        stmt = pg_insert(self.users).values(**record).on_conflict_do_update(
            index_elements=["email"],
            set_={
                "full_name": full_name,
                "social_provider": social_provider,
                "social_id": social_id,
                "status": "active",
                "updated_at": now,
            },
        )
        with self.engine.begin() as conn:
            conn.execute(stmt)
        # Fetch back to get the actual id (upsert may have kept original id)
        return self.get_user_by_email(email) or _serialize(record)  # type: ignore[return-value]

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        query = select(self.users).where(self.users.c.email == email)
        with self.engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _serialize(dict(row)) if row else None

    def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        query = select(self.users).where(self.users.c.id == user_id)
        with self.engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _serialize(dict(row)) if row else None

    def upsert_user_profile(
        self,
        *,
        user_id: str,
        resume_data: Optional[Dict[str, Any]] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        record: Dict[str, Any] = {
            "user_id": user_id,
            "updated_at": now,
        }
        if resume_data is not None:
            record["resume_data"] = resume_data
        if preferences is not None:
            record["preferences"] = preferences
        set_clause: Dict[str, Any] = {"updated_at": now}
        if resume_data is not None:
            set_clause["resume_data"] = resume_data
        if preferences is not None:
            set_clause["preferences"] = preferences
        stmt = pg_insert(self.user_profiles).values(
            user_id=user_id,
            resume_data=resume_data,
            onboarding_metadata=None,
            preferences=preferences,
            embedding=None,
            updated_at=now,
        ).on_conflict_do_update(index_elements=["user_id"], set_=set_clause)
        with self.engine.begin() as conn:
            conn.execute(stmt)

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        query = select(self.user_profiles).where(self.user_profiles.c.user_id == user_id)
        with self.engine.connect() as conn:
            row = conn.execute(query).mappings().first()
        return _serialize(dict(row)) if row else None

    def get_career_analytics(self) -> Dict[str, Any]:
        with self.engine.connect() as conn:
            total_resume_analyses = conn.execute(
                select(text("count(*)")).select_from(self.resume_analyses)
            ).scalar_one()
            total_templates = conn.execute(
                select(text("count(*)")).select_from(self.resume_templates)
            ).scalar_one()
            total_job_queries = conn.execute(
                select(text("count(*)")).select_from(self.career_queries)
            ).scalar_one()
            total_job_results = conn.execute(
                select(text("count(*)")).select_from(self.job_search_results)
            ).scalar_one()
            avg_match_score = conn.execute(
                select(text("coalesce(avg(match_score), 0)")).select_from(self.resume_analyses)
            ).scalar_one()

            source_rows = conn.execute(
                text(
                    "SELECT source, COUNT(*) AS count "
                    "FROM job_search_results "
                    "WHERE source IS NOT NULL "
                    "GROUP BY source "
                    "ORDER BY count DESC "
                    "LIMIT 10"
                )
            ).mappings().all()
            sources = {row["source"]: int(row["count"]) for row in source_rows}
            quality_row = conn.execute(
                text(
                    """
                    SELECT
                        COUNT(*) AS total_evaluations,
                        COALESCE(AVG(grounding_score), 0) AS avg_grounding_score,
                        COALESCE(AVG(citation_count), 0) AS avg_citation_count,
                        COALESCE(SUM(CASE WHEN drift_flag THEN 1 ELSE 0 END), 0) AS drift_alerts
                    FROM response_quality_metrics
                    """
                )
            ).mappings().first()
            quality = dict(quality_row or {})

        return {
            "total_resume_analyses": int(total_resume_analyses or 0),
            "total_templates": int(total_templates or 0),
            "total_job_queries": int(total_job_queries or 0),
            "total_job_results": int(total_job_results or 0),
            "average_match_score": round(float(avg_match_score or 0.0), 2),
            "top_sources": sources,
            "quality_total_evaluations": int(quality.get("total_evaluations") or 0),
            "quality_avg_grounding_score": round(float(quality.get("avg_grounding_score") or 0.0), 2),
            "quality_avg_citation_count": round(float(quality.get("avg_citation_count") or 0.0), 2),
            "quality_drift_alerts": int(quality.get("drift_alerts") or 0),
        }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _str(name: str, **kwargs: Any) -> Column:
    return Column(name, String, **kwargs)


def _serialize(row: Dict[str, Any]) -> Dict[str, Any]:
    return {
        k: v.isoformat() if isinstance(v, datetime) else v
        for k, v in row.items()
    }
