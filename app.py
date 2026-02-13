from __future__ import annotations

import copy
import os
import re
import sqlite3
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

try:
    from .builder import PipelineConfig, run_pipeline
except ImportError:
    from builder import PipelineConfig, run_pipeline

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("DATA_DIR", "/data")).expanduser().resolve()
DEFAULT_DB_PATH = DATA_DIR / "dblp.sqlite"

# Bootstrap pipeline config
DEFAULT_XML_GZ_URL = os.getenv("DBLP_XML_GZ_URL", "https://dblp.org/xml/dblp.xml.gz")
DEFAULT_DTD_URL = os.getenv("DBLP_DTD_URL", "https://dblp.org/xml/dblp.dtd")
DEFAULT_MODE_ENV = os.getenv("DEFAULT_BUILD_MODE", "fullmeta").strip().lower()
DEFAULT_MODE = DEFAULT_MODE_ENV if DEFAULT_MODE_ENV in {"base", "fullmeta"} else "fullmeta"
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
DEFAULT_PROGRESS_EVERY = int(os.getenv("PROGRESS_EVERY", "10000"))
MAX_LOG_LINES = int(os.getenv("MAX_LOG_LINES", "1000"))

# Query service config
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()
DB_BUSY_TIMEOUT_MS = int(os.getenv("DB_BUSY_TIMEOUT_MS", "30000"))
MAX_LIMIT = int(os.getenv("MAX_LIMIT", "200"))
MAX_ENTRIES_PER_SIDE = int(os.getenv("MAX_ENTRIES_PER_SIDE", "120"))
MAX_AUTHOR_RESOLVE = int(os.getenv("MAX_AUTHOR_RESOLVE", "800"))
FULLMETA_PUBLICATION_COLUMNS = {"id", "title", "year", "venue", "pub_type", "raw_xml"}


class StartRequest(BaseModel):
    mode: Literal["base", "fullmeta"] = DEFAULT_MODE  # type: ignore[assignment]
    xml_gz_url: str = Field(default=DEFAULT_XML_GZ_URL, min_length=10)
    dtd_url: str = Field(default=DEFAULT_DTD_URL, min_length=10)
    rebuild: bool = True
    batch_size: int = Field(default=DEFAULT_BATCH_SIZE, ge=100, le=20000)
    progress_every: int = Field(default=DEFAULT_PROGRESS_EVERY, ge=1000, le=500000)


class CoauthoredPairsRequest(BaseModel):
    left: list[str] = Field(default_factory=list)
    right: list[str] = Field(default_factory=list)
    limit_per_pair: int | None = Field(default=None, ge=1, le=5000)
    exact_base_match: bool = True
    author_limit: int | None = Field(default=None, ge=1, le=5000)


@dataclass
class ConsoleState:
    status: Literal["idle", "running", "completed", "stopped", "error"] = "idle"
    step: str = "idle"
    mode: str = DEFAULT_MODE
    message: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] | None = None
    logs: list[str] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_log(message: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"[{ts}] {message}"


def _normalize(text: str) -> str:
    return " ".join(text.split())


def _base_author_name(name: str) -> str:
    match = re.match(r"^(.*?)(?:\s+\d{4})?$", name)
    return match.group(1) if match else name


def _is_base_variant(name: str, base: str) -> bool:
    if name == base:
        return True
    if not name.startswith(base + " "):
        return False
    suffix = name[len(base) + 1 :]
    return len(suffix) == 4 and suffix.isdigit()


def _parse_author_entry(entry: str) -> str:
    text = _normalize(entry)
    for sep in ("||", "|", "::", "\t"):
        if sep in text:
            text = _normalize(text.split(sep, 1)[0])
            break

    while text.endswith(")") and " (" in text:
        prefix, suffix = text.rsplit(" (", 1)
        if not suffix[:-1].strip():
            break
        text = _normalize(prefix)

    return text


def _clamp_limit(limit: int, default: int = 20) -> int:
    if limit <= 0:
        return default
    return min(limit, MAX_LIMIT)


def _sanitize_author_entries(entries: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for entry in entries:
        normalized = _parse_author_entry(entry)
        if not normalized:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned


def _safe_file_info(path: Path) -> dict[str, Any]:
    exists = path.exists()
    size = path.stat().st_size if exists else 0
    return {
        "path": str(path),
        "exists": exists,
        "size_bytes": size,
    }


def _detect_data_date() -> str:
    override = os.getenv("DATA_DATE", "").strip()
    if override:
        return override

    candidates = [DB_PATH, DATA_DIR / "dblp.xml", DATA_DIR / "dblp.xml.gz"]
    for path in candidates:
        if not path.exists():
            continue
        ts = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return ts.strftime("%Y-%m-%d")
    return "unknown"


def _get_connection() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(status_code=503, detail="Database file is not available.")
    try:
        conn = sqlite3.connect(
            str(DB_PATH),
            timeout=max(DB_BUSY_TIMEOUT_MS / 1000.0, 1.0),
            check_same_thread=False,
        )
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"Cannot open database: {exc}") from exc

    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA busy_timeout = {DB_BUSY_TIMEOUT_MS};")
    conn.execute("PRAGMA temp_store = MEMORY;")
    return conn


def _ensure_fullmeta_schema(conn: sqlite3.Connection) -> None:
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type = 'table';")
    tables = {row["name"] for row in cur.fetchall()}
    required = {"publications", "authors", "pub_authors"}
    if not required.issubset(tables):
        raise HTTPException(status_code=503, detail="Database schema is incomplete.")

    cur = conn.cursor()
    cur.execute("PRAGMA table_info(publications);")
    columns = {row["name"] for row in cur.fetchall()}
    missing = FULLMETA_PUBLICATION_COLUMNS - columns
    if missing:
        raise HTTPException(
            status_code=503,
            detail=(
                "Current database is not fullmeta-compatible. "
                f"Missing columns: {', '.join(sorted(missing))}"
            ),
        )


def _resolve_author_ids(
    conn: sqlite3.Connection,
    name_query: str,
    limit: int | None = None,
    exact_base_match: bool = False,
) -> list[int]:
    normalized = _normalize(name_query)
    base = _base_author_name(normalized)
    cur = conn.cursor()

    cur.execute(
        "SELECT id, name FROM authors WHERE name = ? OR name LIKE ?;",
        (base, f"{base} %"),
    )
    exact = [row["id"] for row in cur.fetchall() if _is_base_variant(row["name"], base)]
    if exact_base_match:
        return exact

    limit_sql = "" if limit is None else "LIMIT ?"
    params: tuple[Any, ...] = (normalized, f"%{normalized}%")
    if limit is not None:
        params = (normalized, f"%{normalized}%", limit)

    try:
        cur.execute(
            f"""
            SELECT a.id
            FROM author_fts af
            JOIN authors a ON a.id = af.rowid
            WHERE author_fts MATCH ?
            UNION
            SELECT a.id
            FROM authors a
            WHERE a.name LIKE ?
            {limit_sql};
            """,
            params,
        )
        fuzzy = [row["id"] for row in cur.fetchall()]
    except sqlite3.OperationalError:
        params_like: tuple[Any, ...] = (f"%{normalized}%",)
        if limit is not None:
            params_like = (f"%{normalized}%", limit)
        cur.execute(
            f"""
            SELECT a.id
            FROM authors a
            WHERE a.name LIKE ?
            {limit_sql};
            """,
            params_like,
        )
        fuzzy = [row["id"] for row in cur.fetchall()]

    seen: set[int] = set()
    combined: list[int] = []
    for author_id in exact + fuzzy:
        if author_id in seen:
            continue
        seen.add(author_id)
        combined.append(author_id)
    return combined


def _placeholders(values: list[int]) -> str:
    return ",".join("?" for _ in values)


class PipelineManager:
    def __init__(self) -> None:
        self._state = ConsoleState()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    def _is_running_locked(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def _append_log_locked(self, message: str) -> None:
        self._state.logs.append(_fmt_log(message))
        if len(self._state.logs) > MAX_LOG_LINES:
            self._state.logs = self._state.logs[-MAX_LOG_LINES:]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            state = copy.deepcopy(self._state)
            running = self._is_running_locked()
        return {
            "status": state.status,
            "step": state.step,
            "mode": state.mode,
            "message": state.message,
            "started_at": state.started_at,
            "finished_at": state.finished_at,
            "progress": state.progress,
            "result": state.result,
            "logs": state.logs,
            "running": running,
        }

    def start(self, req: StartRequest) -> dict[str, Any]:
        with self._lock:
            if self._is_running_locked():
                raise HTTPException(status_code=409, detail="A pipeline is already running.")

            self._state = ConsoleState(
                status="running",
                step="prepare",
                mode=req.mode,
                message="Pipeline started.",
                started_at=_now_iso(),
                finished_at=None,
                progress={},
                result=None,
                logs=[],
            )
            self._append_log_locked("Pipeline accepted.")
            self._append_log_locked(f"Mode={req.mode}, rebuild={req.rebuild}")
            self._stop_event.clear()

            config = PipelineConfig(
                xml_gz_url=req.xml_gz_url,
                dtd_url=req.dtd_url,
                data_dir=DATA_DIR,
                mode=req.mode,
                batch_size=req.batch_size,
                progress_every=req.progress_every,
                rebuild=req.rebuild,
            )

            thread = threading.Thread(
                target=self._run_job,
                args=(config,),
                name="dblp-bootstrap-worker",
                daemon=True,
            )
            self._thread = thread
            thread.start()

        return {"accepted": True, "status": "running"}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self._is_running_locked():
                return {"stopping": False, "detail": "No running pipeline."}
            self._stop_event.set()
            self._append_log_locked("Stop signal sent.")
            self._state.message = "Stopping..."
        return {"stopping": True}

    def reset(self) -> dict[str, Any]:
        with self._lock:
            if self._is_running_locked():
                raise HTTPException(status_code=409, detail="Cannot reset while running.")
            self._state = ConsoleState()
            self._append_log_locked("State reset.")
        return {"reset": True}

    def _run_job(self, config: PipelineConfig) -> None:
        def log_cb(message: str) -> None:
            with self._lock:
                self._append_log_locked(message)

        def progress_cb(step: str, payload: dict[str, Any]) -> None:
            with self._lock:
                self._state.step = step
                self._state.progress.update(payload)
                self._state.message = f"Running: {step}"

        def should_stop() -> bool:
            return self._stop_event.is_set()

        try:
            result = run_pipeline(
                config=config,
                log=log_cb,
                progress=progress_cb,
                should_stop=should_stop,
            )
            with self._lock:
                self._state.status = "completed"
                self._state.step = "done"
                self._state.message = "Pipeline completed."
                self._state.result = result
                self._state.finished_at = _now_iso()
                self._append_log_locked("Pipeline completed successfully.")
        except InterruptedError as exc:
            with self._lock:
                self._state.status = "stopped"
                self._state.step = "stopped"
                self._state.message = str(exc)
                self._state.finished_at = _now_iso()
                self._append_log_locked(str(exc))
        except Exception as exc:
            with self._lock:
                self._state.status = "error"
                self._state.step = "error"
                self._state.message = str(exc)
                self._state.finished_at = _now_iso()
                self._append_log_locked(f"Pipeline error: {exc}")


app = FastAPI(
    title="CoAuthors Bootstrap Console",
    description="Query coauthorship and bootstrap DBLP database in one lightweight web app.",
    version="2.1.0",
)

manager = PipelineManager()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/console", response_class=HTMLResponse)
def console(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("console.html", {"request": request})


@app.get("/bootstrap", response_class=HTMLResponse)
def bootstrap_console(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "bootstrap.html",
        {
            "request": request,
            "default_mode": DEFAULT_MODE,
            "default_xml_gz_url": DEFAULT_XML_GZ_URL,
            "default_dtd_url": DEFAULT_DTD_URL,
            "default_batch_size": DEFAULT_BATCH_SIZE,
            "default_progress_every": DEFAULT_PROGRESS_EVERY,
            "data_dir": str(DATA_DIR),
        },
    )


@app.get("/api/health")
def api_health() -> dict[str, Any]:
    conn = _get_connection()
    try:
        _ensure_fullmeta_schema(conn)
        return {"status": "ok"}
    finally:
        conn.close()


@app.get("/api/stats")
def api_stats() -> dict[str, Any]:
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) AS cnt FROM publications;")
        pub_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM authors;")
        author_count = cur.fetchone()["cnt"]
        return {
            "publications": pub_count,
            "authors": author_count,
            "data_source": "DBLP",
            "data_date": _detect_data_date(),
        }
    finally:
        conn.close()


@app.post("/api/coauthors/pairs")
def api_coauthors_pairs(payload: CoauthoredPairsRequest) -> dict[str, Any]:
    left_entries = _sanitize_author_entries(payload.left)
    right_entries = _sanitize_author_entries(payload.right)
    if not left_entries or not right_entries:
        raise HTTPException(status_code=400, detail="Both left and right author lists are required.")

    if len(left_entries) > MAX_ENTRIES_PER_SIDE or len(right_entries) > MAX_ENTRIES_PER_SIDE:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many authors. Max {MAX_ENTRIES_PER_SIDE} per side is allowed "
                "for a single query."
            ),
        )

    limit_per_pair = (
        None if payload.limit_per_pair is None else _clamp_limit(payload.limit_per_pair, default=20)
    )
    author_limit = payload.author_limit
    if author_limit is not None:
        author_limit = min(author_limit, MAX_AUTHOR_RESOLVE)

    conn = _get_connection()
    try:
        _ensure_fullmeta_schema(conn)

        left_ids: dict[str, list[int]] = {}
        right_ids: dict[str, list[int]] = {}

        for entry in left_entries:
            left_ids[entry] = _resolve_author_ids(
                conn,
                entry,
                limit=author_limit,
                exact_base_match=payload.exact_base_match,
            )

        for entry in right_entries:
            right_ids[entry] = _resolve_author_ids(
                conn,
                entry,
                limit=author_limit,
                exact_base_match=payload.exact_base_match,
            )

        matrix: dict[str, dict[str, int]] = {left: {} for left in left_entries}
        pair_pubs: list[dict[str, Any]] = []
        cur = conn.cursor()

        for left_entry, left_author_ids in left_ids.items():
            for right_entry, right_author_ids in right_ids.items():
                if not left_author_ids or not right_author_ids:
                    items: list[dict[str, Any]] = []
                else:
                    limit_sql = "" if limit_per_pair is None else "LIMIT ?"
                    params: tuple[Any, ...] = (*left_author_ids, *right_author_ids)
                    if limit_per_pair is not None:
                        params = (*params, limit_per_pair)
                    cur.execute(
                        f"""
                        SELECT DISTINCT p.title, p.year, p.venue, p.pub_type
                        FROM pub_authors pa1
                        JOIN pub_authors pa2 ON pa1.pub_id = pa2.pub_id
                        JOIN publications p ON p.id = pa1.pub_id
                        WHERE pa1.author_id IN ({_placeholders(left_author_ids)})
                          AND pa2.author_id IN ({_placeholders(right_author_ids)})
                        {limit_sql};
                        """,
                        params,
                    )
                    rows = cur.fetchall()
                    items = [
                        {
                            "title": row["title"],
                            "year": row["year"],
                            "venue": row["venue"],
                            "pub_type": row["pub_type"],
                        }
                        for row in rows
                    ]

                matrix[left_entry][right_entry] = len(items)
                pair_pubs.append(
                    {
                        "left": left_entry,
                        "right": right_entry,
                        "count": len(items),
                        "items": items,
                    }
                )

        return {
            "mode": "fullmeta",
            "limit_per_pair": limit_per_pair,
            "exact_base_match": payload.exact_base_match,
            "left_authors": left_entries,
            "right_authors": right_entries,
            "matrix": matrix,
            "pair_pubs": pair_pubs,
            "pair_count": len(pair_pubs),
        }
    finally:
        conn.close()


@app.get("/api/config")
def api_config() -> dict[str, Any]:
    return {
        "default_mode": DEFAULT_MODE,
        "default_xml_gz_url": DEFAULT_XML_GZ_URL,
        "default_dtd_url": DEFAULT_DTD_URL,
        "default_batch_size": DEFAULT_BATCH_SIZE,
        "default_progress_every": DEFAULT_PROGRESS_EVERY,
        "data_dir": str(DATA_DIR),
    }


@app.get("/api/state")
def api_state() -> dict[str, Any]:
    return manager.snapshot()


@app.get("/api/files")
def api_files() -> dict[str, Any]:
    return {
        "data_dir": str(DATA_DIR),
        "files": {
            "xml_gz": _safe_file_info(DATA_DIR / "dblp.xml.gz"),
            "xml": _safe_file_info(DATA_DIR / "dblp.xml"),
            "dtd": _safe_file_info(DATA_DIR / "dblp.dtd"),
            "db": _safe_file_info(DATA_DIR / "dblp.sqlite"),
            "db_wal": _safe_file_info(DATA_DIR / "dblp.sqlite-wal"),
            "db_shm": _safe_file_info(DATA_DIR / "dblp.sqlite-shm"),
        },
    }


@app.post("/api/start")
def api_start(req: StartRequest) -> dict[str, Any]:
    return manager.start(req)


@app.post("/api/stop")
def api_stop() -> dict[str, Any]:
    return manager.stop()


@app.post("/api/reset")
def api_reset() -> dict[str, Any]:
    return manager.reset()
