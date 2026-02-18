from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from runtime_store import RuntimeStore

APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8091").strip()
DATA_DIR = Path(os.getenv("COAUTHORS_DATA_DIR", str(BASE_DIR / "data"))).expanduser().resolve()
RUNTIME_DB_PATH = Path(
    os.getenv("COAUTHORS_RUNTIME_DB", str(DATA_DIR / "runtime.sqlite"))
).expanduser().resolve()
runtime_store = RuntimeStore(RUNTIME_DB_PATH)


class RuntimeCacheGetRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=256)


class RuntimeCachePutRequest(BaseModel):
    key: str = Field(..., min_length=1, max_length=256)
    data: dict[str, Any]


class RuntimeQueryEventRequest(BaseModel):
    event_type: str = Field(default="pairs_lookup", min_length=1, max_length=64)
    query_hash: str | None = Field(default=None, max_length=128)
    left_count: int = Field(default=0, ge=0, le=500)
    right_count: int = Field(default=0, ge=0, le=500)
    total_pairs: int = Field(default=0, ge=0, le=250000)
    cache_hit: bool = False
    success: bool = True
    duration_ms: int | None = Field(default=None, ge=0, le=86400000)
    error_message: str | None = Field(default=None, max_length=1000)
    extra: dict[str, Any] | None = None


app = FastAPI(
    title="CoAuthors Frontend",
    description="Frontend renderer for CoAuthors. Backend APIs are served by DblpService.",
    version=APP_VERSION,
)

app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    visit_count = runtime_store.record_page_visit(
        route="/",
        client_ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "visit_count": visit_count,
            "api_base": API_BASE_URL,
        },
    )


@app.get("/api/runtime/stats")
def api_runtime_stats() -> JSONResponse:
    return JSONResponse(runtime_store.stats())


@app.post("/api/runtime/cache/get")
def api_runtime_cache_get(payload: RuntimeCacheGetRequest) -> JSONResponse:
    data = runtime_store.cache_get(payload.key.strip())
    return JSONResponse({"hit": data is not None, "data": data})


@app.post("/api/runtime/cache/put")
def api_runtime_cache_put(payload: RuntimeCachePutRequest) -> JSONResponse:
    key = payload.key.strip()
    if not key:
        raise HTTPException(status_code=400, detail="Cache key is required.")
    runtime_store.cache_put(key, payload.data)
    return JSONResponse({"ok": True})


@app.post("/api/runtime/query/event")
def api_runtime_query_event(payload: RuntimeQueryEventRequest) -> JSONResponse:
    runtime_store.record_query_event(
        event_type=payload.event_type.strip() or "pairs_lookup",
        query_hash=(payload.query_hash or "").strip() or None,
        left_count=payload.left_count,
        right_count=payload.right_count,
        total_pairs=payload.total_pairs,
        cache_hit=payload.cache_hit,
        success=payload.success,
        duration_ms=payload.duration_ms,
        error_message=(payload.error_message or "").strip() or None,
        extra=payload.extra,
    )
    return JSONResponse({"ok": True})
