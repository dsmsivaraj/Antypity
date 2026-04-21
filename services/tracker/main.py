from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
from backend.container import build_container
from backend.database import PostgreSQLDatabaseClient

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ApplicationRecord(BaseModel):
    user_id: str
    job_id: str
    title: str
    company: str
    status: str = "applied" # applied, screening, interview, offer, rejected

class ApplicationResponse(ApplicationRecord):
    id: str
    created_at: str
    updated_at: str

class AnalyticsResponse(BaseModel):
    total_applications: int
    by_status: Dict[str, int]
    by_company: Dict[str, int]
    match_accuracy_avg: float


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    app.state.db = container.database_client
    
    # Define tracking table if not exists (in database.py eventually)
    with app.state.db.engine.begin() as conn:
        from sqlalchemy import Table, Column, String, DateTime, JSON, MetaData
        meta = MetaData()
        app.state.applications = Table(
            "applications",
            meta,
            Column("id", String, primary_key=True),
            Column("user_id", String, nullable=False),
            Column("job_id", String, nullable=False),
            Column("title", String, nullable=False),
            Column("company", String, nullable=False),
            Column("status", String, nullable=False),
            Column("metadata", JSON, nullable=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
        )
        meta.create_all(conn)

    _logger.info("Tracker service started.")
    yield
    _logger.info("Tracker service shutting down.")


app = create_base_app(
    title="Application Tracker Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/tracker/apply", response_model=ApplicationResponse, tags=["tracker"])
async def record_application(request: Request, body: ApplicationRecord):
    db: PostgreSQLDatabaseClient = request.app.state.db
    table = request.app.state.applications
    
    record_id = str(uuid4())
    now = datetime.now(timezone.utc)
    
    with db.engine.begin() as conn:
        from sqlalchemy import insert
        record = {
            "id": record_id,
            **body.model_dump(),
            "created_at": now,
            "updated_at": now
        }
        conn.execute(insert(table).values(**record))
        
    return ApplicationResponse(
        id=record_id,
        **body.model_dump(),
        created_at=now.isoformat(),
        updated_at=now.isoformat()
    )


@app.get("/tracker/user/{user_id}", response_model=List[ApplicationResponse], tags=["tracker"])
async def list_user_applications(request: Request, user_id: str):
    db: PostgreSQLDatabaseClient = request.app.state.db
    table = request.app.state.applications
    
    with db.engine.connect() as conn:
        from sqlalchemy import select
        query = select(table).where(table.c.user_id == user_id).order_by(table.c.updated_at.desc())
        rows = conn.execute(query).mappings().all()
        
    return [
        ApplicationResponse(
            id=r["id"],
            user_id=r["user_id"],
            job_id=r["job_id"],
            title=r["title"],
            company=r["company"],
            status=r["status"],
            created_at=r["created_at"].isoformat(),
            updated_at=r["updated_at"].isoformat()
        )
        for r in rows
    ]

@app.get("/tracker/analytics", response_model=AnalyticsResponse, tags=["analytics"])
async def get_analytics(request: Request):
    db: PostgreSQLDatabaseClient = request.app.state.db
    table = request.app.state.applications
    
    with db.engine.connect() as conn:
        from sqlalchemy import select, func
        
        # 1. Total and status breakdown
        status_query = select(table.c.status, func.count(table.c.id)).group_by(table.c.status)
        status_rows = conn.execute(status_query).all()
        
        # 2. Company breakdown
        company_query = select(table.c.company, func.count(table.c.id)).group_by(table.c.company)
        company_rows = conn.execute(company_query).all()
        
        total = sum(r[1] for r in status_rows)
        
    return AnalyticsResponse(
        total_applications=total,
        by_status={r[0]: r[1] for r in status_rows},
        by_company={r[0]: r[1] for r in company_rows},
        match_accuracy_avg=87.2 # Mocked aggregate
    )
