from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from shared.service_utils.base_service import create_base_app
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


class ProfileResponse(BaseModel):
    user_id: str
    resume_filename: Optional[str] = None
    resume_text: Optional[str] = None
    updated_at: str


class ProfileUpdateRequest(BaseModel):
    resume_filename: Optional[str] = None
    resume_text: Optional[str] = None


# ── Service logic ────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    _logger.info("Identity Service starting up.")
    try:
        container = build_container()
        app.state.container = container
        app.state.db = container.database_client
        _logger.info("Identity Service started successfully.")
    except Exception:
        _logger.critical("Identity Service failed to start.", exc_info=True)
        raise
    yield
    _logger.info("Identity Service shutting down.")


app = create_base_app(
    title="Identity Service",
    version="1.0.0",
    cors_origins=["*"],
    lifespan=lifespan,
)


@app.post("/auth/social", response_model=SessionResponse, tags=["auth"])
async def social_auth(request: Request, body: SocialAuthRequest):
    _logger.info("Social auth attempt: provider=%s email=%s", body.provider, body.email)
    db: PostgreSQLDatabaseClient = request.app.state.db

    try:
        with db.engine.connect() as conn:
            from sqlalchemy import select, insert

            query = select(db.users).where(db.users.c.email == body.email)
            user_row = conn.execute(query).mappings().first()

            if not user_row:
                user_id = str(uuid4())
                new_user = {
                    "id": user_id,
                    "email": body.email,
                    "full_name": body.full_name,
                    "social_provider": body.provider,
                    "social_id": body.social_id,
                    "role": "applicant",
                    "status": "pending",
                    "created_at": datetime.now(timezone.utc),
                    "updated_at": datetime.now(timezone.utc),
                }
                conn.execute(insert(db.users).values(**new_user))
                conn.execute(insert(db.user_profiles).values(
                    user_id=user_id,
                    updated_at=datetime.now(timezone.utc),
                ))
                conn.commit()
                user_row = new_user
                _logger.info("New user created: email=%s provider=%s user_id=%s", body.email, body.provider, user_id)
            else:
                user_row = dict(user_row)
                _logger.info("Existing user login: email=%s provider=%s user_id=%s", body.email, body.provider, user_row["id"])
    except Exception:
        _logger.error("Social auth DB error: provider=%s email=%s", body.provider, body.email, exc_info=True)
        raise HTTPException(status_code=500, detail="Authentication failed.")

    session_id = str(uuid4())
    token = f"session_{uuid4().hex}"
    expires_at = datetime.now(timezone.utc) + timedelta(days=7)

    try:
        with db.engine.begin() as conn:
            from sqlalchemy import insert
            conn.execute(insert(db.user_sessions).values(
                id=session_id,
                user_id=user_row["id"],
                token=token,
                expires_at=expires_at,
                created_at=datetime.now(timezone.utc),
            ))
        _logger.info("Session created: user_id=%s session_id=%s expires=%s", user_row["id"], session_id, expires_at)
    except Exception:
        _logger.error("Failed to create session: user_id=%s", user_row["id"], exc_info=True)
        raise HTTPException(status_code=500, detail="Session creation failed.")

    user_resp = UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        full_name=user_row["full_name"],
        role=user_row["role"],
        status=user_row["status"],
        created_at=(
            user_row["created_at"].isoformat()
            if isinstance(user_row["created_at"], datetime)
            else user_row["created_at"]
        ),
    )
    return SessionResponse(access_token=token, user=user_resp)


@app.get("/users/me", response_model=UserResponse, tags=["users"])
async def get_me(request: Request, token: str):
    _logger.debug("GET /users/me: token lookup")
    db: PostgreSQLDatabaseClient = request.app.state.db

    try:
        with db.engine.connect() as conn:
            from sqlalchemy import select
            query = (
                select(db.users)
                .join(db.user_sessions, db.users.c.id == db.user_sessions.c.user_id)
                .where(
                    db.user_sessions.c.token == token,
                    db.user_sessions.c.expires_at > datetime.now(timezone.utc),
                )
            )
            user_row = conn.execute(query).mappings().first()
    except Exception:
        _logger.error("DB error on /users/me token lookup.", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error.")

    if not user_row:
        _logger.warning("Invalid or expired token used on GET /users/me.")
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    _logger.debug("User resolved: user_id=%s email=%s", user_row["id"], user_row["email"])
    return UserResponse(
        id=user_row["id"],
        email=user_row["email"],
        full_name=user_row["full_name"],
        role=user_row["role"],
        status=user_row["status"],
        created_at=user_row["created_at"].isoformat(),
    )


@app.get("/users/me/profile", response_model=ProfileResponse, tags=["users"])
async def get_my_profile(request: Request, token: str):
    _logger.debug("GET /users/me/profile: token lookup")
    db: PostgreSQLDatabaseClient = request.app.state.db

    try:
        with db.engine.connect() as conn:
            from sqlalchemy import select
            query = (
                select(db.user_profiles)
                .join(db.user_sessions, db.user_profiles.c.user_id == db.user_sessions.c.user_id)
                .where(
                    db.user_sessions.c.token == token,
                    db.user_sessions.c.expires_at > datetime.now(timezone.utc),
                )
            )
            profile_row = conn.execute(query).mappings().first()
    except Exception:
        _logger.error("DB error on /users/me/profile token lookup.", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal error.")

    if not profile_row:
        _logger.warning("Invalid or expired token used on GET /users/me/profile.")
        raise HTTPException(status_code=401, detail="Invalid or expired session.")

    _logger.debug("Profile resolved: user_id=%s", profile_row["user_id"])
    return ProfileResponse(
        user_id=profile_row["user_id"],
        resume_filename=profile_row.get("resume_filename"),
        resume_text=profile_row.get("resume_text"),
        updated_at=profile_row["updated_at"].isoformat(),
    )


@app.patch("/users/me/profile", tags=["users"])
async def update_my_profile(request: Request, body: ProfileUpdateRequest, token: str):
    fields = list(body.model_dump(exclude_unset=True).keys())
    _logger.info("PATCH /users/me/profile: fields=%s", fields)
    db: PostgreSQLDatabaseClient = request.app.state.db

    try:
        with db.engine.begin() as conn:
            from sqlalchemy import update, select

            session_query = select(db.user_sessions.c.user_id).where(
                db.user_sessions.c.token == token,
                db.user_sessions.c.expires_at > datetime.now(timezone.utc),
            )
            user_id = conn.execute(session_query).scalar()

            if not user_id:
                _logger.warning("Profile update rejected: invalid/expired token.")
                raise HTTPException(status_code=401, detail="Invalid or expired session.")

            values = body.model_dump(exclude_unset=True)
            values["updated_at"] = datetime.now(timezone.utc)
            conn.execute(
                update(db.user_profiles)
                .where(db.user_profiles.c.user_id == user_id)
                .values(**values)
            )
        _logger.info("Profile updated: user_id=%s fields=%s", user_id, fields)
    except HTTPException:
        raise
    except Exception:
        _logger.error("Failed to update profile.", exc_info=True)
        raise HTTPException(status_code=500, detail="Profile update failed.")

    return {"message": "Profile updated successfully."}
