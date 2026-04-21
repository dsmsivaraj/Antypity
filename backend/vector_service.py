from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel
import os

from .embeddings_service import get_embedding_service, configure_embedding_service

_logger = logging.getLogger(__name__)

def _verify_api_key(x_api_key: str = Header(None)):
    expected = os.getenv("VECTOR_API_KEY")
    # If no key configured, allow unauthenticated access (dev mode)
    if expected:
        if not x_api_key or x_api_key != expected:
            raise HTTPException(status_code=401, detail="Invalid API key")
    return True

# Rate limiting and metrics
from .ratelimit import check_rate_limit
from .metrics import count_encode, count_query, record_retrieval_hit

app = FastAPI(title="Actypity Vector Service", dependencies=[Depends(_verify_api_key), Depends(check_rate_limit)])

# Simple middleware to count encode/query requests for observability
@app.middleware("http")
async def _metrics_middleware(request, call_next):
    path = request.url.path or ""
    try:
        if path.startswith("/encode"):
            try:
                count_encode()
            except Exception:
                pass
        elif path.startswith("/query"):
            try:
                count_query()
            except Exception:
                pass
    except Exception:
        pass
    response = await call_next(request)
    return response


# Initialize singleton embedding service on first import
# Initialize embedding service and optionally wire a DB client for metrics
from .config import Settings
from .database import PostgreSQLDatabaseClient

settings = Settings.from_env()
_db_client = None
try:
    if settings.postgres_dsn or settings.postgres_host:
        _db_client = PostgreSQLDatabaseClient(settings)
except Exception:
    _db_client = None

# Configure the embedding service singleton with DB client if available
svc = configure_embedding_service(database_client=_db_client)

class EncodeRequest(BaseModel):
    texts: List[str]

class EncodeResponse(BaseModel):
    embeddings: List[List[float]]

class IndexRequest(BaseModel):
    doc_id: str
    section_id: str
    text: str

class QueryRequest(BaseModel):
    text: str
    top_k: Optional[int] = 5

@app.get("/health")
async def health():
    return {"status": "ok", "service": "vector-service"}

@app.get("/status")
async def status():
    try:
        return svc.status()
    except Exception as exc:
        _logger.exception("Failed status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/encode", response_model=EncodeResponse)
async def encode(req: EncodeRequest):
    try:
        embs = svc.encode(req.texts)
        return EncodeResponse(embeddings=embs)
    except Exception as exc:
        _logger.exception("Encode failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/index")
async def index(req: IndexRequest):
    try:
        svc.index_document(req.doc_id, req.section_id, req.text)
        return {"ok": True}
    except Exception as exc:
        _logger.exception("Index failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

@app.post("/query")
async def query(req: QueryRequest):
    try:
        res = svc.query(req.text, top_k=req.top_k or 5)
        return {"results": res}
    except Exception as exc:
        _logger.exception("Query failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8600)
