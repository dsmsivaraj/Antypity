from __future__ import annotations

import hashlib
import logging
import secrets
from typing import Dict, Optional

from fastapi import HTTPException, status

from .database import PostgreSQLDatabaseClient

_logger = logging.getLogger(__name__)

VALID_ROLES = {"admin", "operator", "viewer"}

# None means unrestricted (admin); a set means the allowed permissions for that role.
ROLE_PERMISSIONS: Dict[str, Optional[set]] = {
    "admin": None,
    "operator": {
        "execute",
        "agents:read",
        "executions:read",
        "health",
        "metrics:read",
        "workflows:execute",
        "workflows:read",
        "logs:read",
    },
    "viewer": {
        "agents:read",
        "executions:read",
        "health",
        "metrics:read",
        "workflows:read",
        "logs:read",
    },
}


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def generate_key() -> str:
    return f"act_{secrets.token_urlsafe(32)}"


class AuthService:
    def __init__(self, db: PostgreSQLDatabaseClient, config_enabled: bool = True) -> None:
        self.db = db
        # Auth only works when the database is reachable; disable silently otherwise.
        self.enabled = config_enabled and db.is_configured
        if config_enabled and not db.is_configured:
            _logger.warning(
                "AUTH_ENABLED=true but PostgreSQL is not configured — "
                "authentication is disabled for this session."
            )

    def validate_key(self, raw_key: str) -> Optional[Dict]:
        if not self.enabled:
            return {"id": "anonymous", "name": "anonymous", "role": "admin"}
        try:
            return self.db.get_api_key_by_hash(hash_key(raw_key))
        except Exception as exc:
            _logger.error("API key validation failed: %s", exc)
            return None

    def bootstrap_required(self) -> bool:
        if not self.enabled:
            return False
        try:
            return not self.db.has_any_api_key()
        except Exception as exc:
            _logger.error("Could not determine bootstrap status: %s", exc)
            return False

    def check_permission(self, principal: Dict, permission: str) -> None:
        role = principal.get("role", "viewer")
        allowed = ROLE_PERMISSIONS.get(role)
        if allowed is None:  # admin — unrestricted
            return
        if permission not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{role}' does not have permission '{permission}'.",
            )

    def create_key(self, name: str, role: str) -> Dict:
        if role not in VALID_ROLES:
            raise ValueError(f"Invalid role '{role}'. Choose from: {', '.join(sorted(VALID_ROLES))}")
        raw_key = generate_key()
        record = self.db.create_api_key(name=name, role=role, key_hash=hash_key(raw_key))
        return {**record, "key": raw_key}

    def seed_default_admin(self, raw_key: str, name: str = "default-admin") -> None:
        if not self.enabled:
            return
        try:
            if self.db.has_any_api_key():
                return
            self.db.create_api_key(name=name, role="admin", key_hash=hash_key(raw_key))
            _logger.info("Seeded default admin API key (name='%s').", name)
        except Exception as exc:
            _logger.error("Failed to seed default admin key: %s", exc)

    def bootstrap_admin(self, provided_token: str, configured_token: Optional[str], name: str) -> Dict:
        if not self.enabled:
            raise ValueError("Auth is disabled.")
        if not configured_token:
            raise ValueError("Bootstrap token is not configured.")
        if not secrets.compare_digest(provided_token, configured_token):
            raise PermissionError("Invalid bootstrap token.")
        if self.db.has_any_api_key():
            raise RuntimeError("Bootstrap is no longer available because API keys already exist.")
        return self.create_key(name=name, role="admin")
