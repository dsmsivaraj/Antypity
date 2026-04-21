from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Dict

from jose import JWTError, jwt

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def _secret() -> str:
    from .config import get_settings
    return get_settings().secret_key


def create_access_token(data: Dict) -> str:
    payload = dict(data)
    payload["exp"] = datetime.now(timezone.utc) + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    return jwt.encode(payload, _secret(), algorithm=ALGORITHM)


def decode_access_token(token: str) -> Dict:
    """Decode and verify a JWT. Raises jose.JWTError on failure."""
    return jwt.decode(token, _secret(), algorithms=[ALGORITHM])
