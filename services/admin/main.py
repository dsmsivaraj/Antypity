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
    _logger.info("Admin Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        app.state.db = container.database_client
        _logger.info("Admin Service started successfully.")
    except Exception:
        _logger.critical("Admin Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Admin Service shutting down.")


app = create_base_app(
    title="Admin Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.get("/admin/users", response_model=List[UserAdminResponse], tags=["admin"])
async def list_users(request: Request, _: bool = Depends(_require_internal)):
    _logger.info("Admin: listing all users.")
    db: PostgreSQLDatabaseClient = request.app.state.db

    try:
        with db.engine.connect() as conn:
            from sqlalchemy import select
            query = select(db.users).order_by(db.users.c.created_at.desc())
            rows = conn.execute(query).mappings().all()
        _logger.info("Admin: returned %d users.", len(rows))
    except Exception:
        _logger.error("Admin: failed to list users.", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to fetch users.")

    return [
        UserAdminResponse(
            id=r["id"],
            email=r["email"],
            full_name=r["full_name"],
            role=r["role"],
            status=r["status"],
            created_at=r["created_at"].isoformat(),
        )
        for r in rows
    ]


@app.post("/admin/approve", tags=["admin"])
async def approve_user(request: Request, body: ApprovalRequest, _: bool = Depends(_require_internal)):
    _logger.info("Admin: approving user_id=%s new_status=%s", body.user_id, body.status)
    db: PostgreSQLDatabaseClient = request.app.state.db

    try:
        with db.engine.begin() as conn:
            from sqlalchemy import update
            result = conn.execute(
                update(db.users)
                .where(db.users.c.id == body.user_id)
                .values(status=body.status)
            )

        if result.rowcount == 0:
            _logger.warning("Admin: user not found for approval: user_id=%s", body.user_id)
            raise HTTPException(status_code=404, detail="User not found.")

        _logger.info("Admin: user status updated: user_id=%s status=%s", body.user_id, body.status)
    except HTTPException:
        raise
    except Exception:
        _logger.error("Admin: failed to approve user_id=%s", body.user_id, exc_info=True)
        raise HTTPException(status_code=500, detail="User approval failed.")

    return {"message": f"User status updated to {body.status}."}


@app.get("/admin/security-groups", response_model=List[SecurityGroupResponse], tags=["admin"])
async def list_security_groups(request: Request, _: bool = Depends(_require_internal)):
    _logger.debug("Admin: listing security groups.")
    return [
        SecurityGroupResponse(name="admin", permissions=["*"]),
        SecurityGroupResponse(name="recruiter", permissions=["resume:read", "job:write", "outreach:send"]),
        SecurityGroupResponse(name="applicant", permissions=["resume:write", "job:read", "tracker:read"]),
    ]
