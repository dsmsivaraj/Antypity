from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
from backend.container import build_container
from backend.database import PostgreSQLDatabaseClient

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class UserAdminResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    status: str
    created_at: str

class ApprovalRequest(BaseModel):
    user_id: str
    status: str  # approved, active, disabled

class SecurityGroupResponse(BaseModel):
    name: str
    permissions: List[str]


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    app.state.db = container.database_client
    _logger.info("Admin service started.")
    yield
    _logger.info("Admin service shutting down.")


app = create_base_app(
    title="Admin Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.get("/admin/users", response_model=List[UserAdminResponse], tags=["admin"])
async def list_users(request: Request, _: bool = Depends(_require_internal)):
    db: PostgreSQLDatabaseClient = request.app.state.db
    
    with db.engine.connect() as conn:
        from sqlalchemy import select
        query = select(db.users).order_by(db.users.c.created_at.desc())
        rows = conn.execute(query).mappings().all()
        
    return [
        UserAdminResponse(
            id=r["id"],
            email=r["email"],
            full_name=r["full_name"],
            role=r["role"],
            status=r["status"],
            created_at=r["created_at"].isoformat()
        )
        for r in rows
    ]


@app.post("/admin/approve", tags=["admin"])
async def approve_user(request: Request, body: ApprovalRequest, _: bool = Depends(_require_internal)):
    db: PostgreSQLDatabaseClient = request.app.state.db
    
    with db.engine.begin() as conn:
        from sqlalchemy import update
        stmt = (
            update(db.users)
            .where(db.users.c.id == body.user_id)
            .values(status=body.status)
        )
        result = conn.execute(stmt)
        
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="User not found.")
        
    return {"message": f"User status updated to {body.status}."}


@app.get("/admin/security-groups", response_model=List[SecurityGroupResponse], tags=["admin"])
async def list_security_groups(request: Request, _: bool = Depends(_require_internal)):
    # Hardcoded for now, could be in DB
    return [
        SecurityGroupResponse(name="admin", permissions=["*"]),
        SecurityGroupResponse(name="recruiter", permissions=["resume:read", "job:write", "outreach:send"]),
        SecurityGroupResponse(name="applicant", permissions=["resume:write", "job:read", "tracker:read"]),
    ]
