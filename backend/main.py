"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.portal import router as portal_router
from backend.api.runs import router as runs_router
from backend.config import CORS_ORIGINS, EVIDENCE_DIR, IT_OPS_DB_PATH
from backend.db.connection import connect
from backend.db.schema import init_schema
from backend.events.publisher import get_event_publisher


@asynccontextmanager
async def lifespan(app: FastAPI):
    IT_OPS_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    conn = connect()
    try:
        init_schema(conn)
    finally:
        conn.close()

    import asyncio

    get_event_publisher().set_loop(asyncio.get_running_loop())
    yield


app = FastAPI(title="IT Ops API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(portal_router)
app.include_router(runs_router)


@app.get("/health")
def health():
    return {"status": "ok"}
