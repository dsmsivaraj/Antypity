from __future__ import annotations

import os
from time import time
from fastapi import Header, HTTPException

# Simple per-api-key per-minute rate limiter (in-memory, dev-only)
RATE_LIMIT_PER_MIN = int(os.getenv("VECTOR_RATE_LIMIT_PER_MIN", "60"))

# key: (api_key, minute) -> count
_hits: dict = {}


def is_allowed(x_api_key: str | None) -> bool:
    now_min = int(time() // 60)
    key = (x_api_key or "anon", now_min)
    count = _hits.get(key, 0)
    if count >= RATE_LIMIT_PER_MIN:
        return False
    _hits[key] = count + 1
    # cleanup old keys (best effort)
    if len(_hits) > 10000:
        # remove keys older than 5 minutes
        cutoff = now_min - 5
        keys_to_del = [k for k in _hits.keys() if k[1] < cutoff]
        for k in keys_to_del:
            del _hits[k]
    return True


def check_rate_limit(x_api_key: str = Header(None)) -> bool:
    allowed = is_allowed(x_api_key)
    if not allowed:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    return True
