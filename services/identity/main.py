from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from shared.service_utils.base_service import _require_internal, create_base_app
from backend.container import build_container
from backend.database import PostgreSQLDatabaseClient

_logger = logging.getLogger(__name__)


# ── Schemas ──────────────────────────────────────────────────────────────────

class SocialAuthRequest(BaseModel):
    provider: str  # google, facebook, instagram
    token: str
    email: str
    full_name: Optional[str] = None
    social_id: str

class UserResponse(BaseModel):
    id: str
    email: str
    full_name: Optional[str]
    role: str
    status: str
    created_at: str

class SessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    container = build_container()
    app.state.container = container
    app.state.db = container.database_client
    _logger.info("Identity service started.")
    yield
    _logger.info("Identity service shutting down.")


app = create_base_app(
    title="Identity Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/auth/social", response_model=SessionResponse, tags=["auth"])
async def social_auth(request: Request, body: SocialAuthRequest):
    db: PostgreSQLDatabaseClient = request.app.state.db
    
    # 1. Check if user exists
    with db.engine.connect() as conn:
        from sqlalchemy import select, insert, update
        
        query = select(db.users).where(db.users.c.email == body.email)
        user_row = conn.execute(query).mappings().first()
        
        if not user_row:
            # 2. Create user if not exists (Onboarding)
            user_id = str(uuid4())
            new_user = {
                "id": user_id,
                "email": body.email,
                "full_name": body.full_name,
                "social_provider": body.provider,
                "social_id": body.social_id,
                "role": "applicant",  # Default role
                "status": "pending",   # Needs approval
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc),
            }
            conn.execute(insert(db.users).values(**new_user))
            # Create profile
            conn.execute(insert(db.user_profiles).values(
                user_id=user_id,
                updated_at=datetime.now(timezone.utc)
            ))
            conn.commit()
            user_row = new_user
        else:
            user_row = dict(user_row)

    # 3. Create Session
    session_id = str(uuid4())
    token = f"session_{uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)
    
    with db.engine.begin() as conn:
        conn.execute(insert(db.user_sessions).values(
            id=session_id,
            user_id=user_row["id"],
            token=token,
            expires_at=expires_at,
            created_at=datetime.now(timezone.utc)
        ))

    user_resp = UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        full_name=user_row["full_name"],
        role=user_row["role"],
        status=user_row["status"],
        created_at=user_row["created_at"].isoformat() if isinstance(user_row["created_at"], datetime) else user_row["created_at"]
    )

    return SessionResponse(access_token=token, user=user_resp)


@app.get("/users/me", response_model=UserResponse, tags=["users"])
async def get_me(request: Request, token: str):
    db: PostgreSQLDatabaseClient = request.app.state.db
    
    with db.engine.connect() as conn:
        from sqlalchemy import select
        # Join session with users
        query = (
            select(db.users)
            .join(db.user_sessions, db.users.c.id == db.user_sessions.c.user_id)
            .where(db.user_sessions.c.token == token, db.user_sessions.c.expires_at > datetime.now(timezone.utc))
        )
        user_row = conn.execute(query).mappings().first()
        
    if not user_row:
        raise HTTPException(status_code=401, detail="Invalid or expired session.")
        
    return UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        full_name=user_row["full_name"],
        role=user_row["role"],
        status=user_row["status"],
        created_at=user_row["created_at"].isoformat()
    )
