from __future__ import annotations

import copy
import csv
import hashlib
import json
import logging
import os
import re
import secrets
import sqlite3
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Literal

from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

try:
    from .builder import PipelineConfig, run_pipeline
except ImportError:
    from builder import PipelineConfig, run_pipeline

APP_VERSION = "1.0.0"

BASE_DIR = Path(__file__).resolve().parent

# Load PC members from CSV (served as a static file, also read at startup for the API)
_PC_MEMBERS_CSV = BASE_DIR / "static" / "pc-members.csv"
PC_MEMBERS: list[dict[str, str]] = []
if _PC_MEMBERS_CSV.exists():
    with open(_PC_MEMBERS_CSV, newline="", encoding="utf-8-sig") as _f:
        for _row in csv.DictReader(_f):
            name = (_row.get("reviewer") or "").strip()
            affiliation = (_row.get("affiliation") or "").strip()
            if name:
                PC_MEMBERS.append({"name": name, "affiliation": affiliation})

if "DATA_DIR" in os.environ:
    DATA_DIR = Path(os.environ["DATA_DIR"]).expanduser().resolve()
else:
    # Default to the repository directory (same place as app.py / dblp.sqlite / dblp.xml* for local dev).
    # Docker explicitly sets DATA_DIR=/data, so this won't affect container deployments.
    DATA_DIR = BASE_DIR
DEFAULT_DB_PATH = DATA_DIR / "dblp.sqlite"

# Bootstrap pipeline config
DEFAULT_XML_GZ_URL = os.getenv("DBLP_XML_GZ_URL", "https://dblp.org/xml/dblp.xml.gz")
DEFAULT_DTD_URL = os.getenv("DBLP_DTD_URL", "https://dblp.org/xml/dblp.dtd")
DEFAULT_MODE = "fullmeta"
DEFAULT_BATCH_SIZE = int(os.getenv("BATCH_SIZE", "1000"))
DEFAULT_PROGRESS_EVERY = int(os.getenv("PROGRESS_EVERY", "10000"))
MAX_LOG_LINES = int(os.getenv("MAX_LOG_LINES", "1000"))

# Query service config
DB_PATH = Path(os.getenv("DB_PATH", str(DEFAULT_DB_PATH))).expanduser().resolve()
DB_BUSY_TIMEOUT_MS = int(os.getenv("DB_BUSY_TIMEOUT_MS", "30000"))
MAX_LIMIT = int(os.getenv("MAX_LIMIT", "200"))
MAX_ENTRIES_PER_SIDE = min(int(os.getenv("MAX_ENTRIES_PER_SIDE", "50")), 50)
MAX_AUTHOR_RESOLVE = int(os.getenv("MAX_AUTHOR_RESOLVE", "800"))
FULLMETA_PUBLICATION_COLUMNS = {"id", "title", "year", "venue", "pub_type", "raw_xml"}

try:
    HEALTH_CACHE_TTL_SEC = max(float(os.getenv("HEALTH_CACHE_TTL_SEC", "3")), 0.0)
except ValueError:
    HEALTH_CACHE_TTL_SEC = 3.0

MAX_CONCURRENT_QUERIES = max(int(os.getenv("COAUTHORS_MAX_CONCURRENT_QUERIES", "4")), 1)
QUERY_ACQUIRE_TIMEOUT_SEC = max(float(os.getenv("COAUTHORS_QUERY_ACQUIRE_TIMEOUT_SEC", "0")), 0.0)
_query_semaphore = threading.BoundedSemaphore(value=MAX_CONCURRENT_QUERIES)

BOOTSTRAP_USERNAME = os.getenv("BOOTSTRAP_USERNAME", "admin")
BOOTSTRAP_PASSWORD = os.getenv("BOOTSTRAP_PASSWORD", "changeme")
_http_basic = HTTPBasic()


def _verify_bootstrap_auth(
    credentials: HTTPBasicCredentials = Depends(_http_basic),
) -> str:
    username_ok = secrets.compare_digest(
        credentials.username.encode("utf-8"),
        BOOTSTRAP_USERNAME.encode("utf-8"),
    )
    password_ok = secrets.compare_digest(
        credentials.password.encode("utf-8"),
        BOOTSTRAP_PASSWORD.encode("utf-8"),
    )
    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials.",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@dataclass(frozen=True)
class DbSig:
    path: str
    size: int
    mtime_ns: int


@dataclass(slots=True)
class StatsCache:
    lock: threading.Lock = field(default_factory=threading.Lock)
    sig: DbSig | None = None
    value: dict[str, Any] | None = None


@dataclass(slots=True)
class HealthCache:
    lock: threading.Lock = field(default_factory=threading.Lock)
    sig: DbSig | None = None
    expires_at: float = 0.0
    ok: bool = False
    status_code: int = 503
    detail: str | None = None


_stats_cache = StatsCache()
_health_cache = HealthCache()

_page_views_lock = threading.Lock()
_page_views = 0


def _increment_page_views_fallback() -> int:
    global _page_views
    with _page_views_lock:
        _page_views += 1
        return _page_views


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        first = forwarded.split(",", 1)[0].strip()
        return first or forwarded
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    if request.client:
        return request.client.host
    return "unknown"


def _get_user_agent(request: Request) -> str:
    ua = request.headers.get("user-agent", "").strip()
    return ua[:300]


def _init_app_logger() -> logging.Logger:
    logger = logging.getLogger("coauthors")
    if logger.handlers:
        return logger

    level_name = os.getenv("COAUTHORS_LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, level_name, logging.INFO)
    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")

    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(level)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)

    try:
        log_path = Path(
            os.getenv("COAUTHORS_LOG_PATH", str(DATA_DIR / "coauthors.log"))
        ).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        max_bytes = int(os.getenv("COAUTHORS_LOG_MAX_BYTES", str(10 * 1024 * 1024)))
        backup_count = int(os.getenv("COAUTHORS_LOG_BACKUP_COUNT", "5"))
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(fmt)
        logger.addHandler(file_handler)
    except Exception:
        logger.exception("Failed to initialize file logging.")

    return logger


logger = _init_app_logger()


def _log_event(event: dict[str, Any], level: int = logging.INFO) -> None:
    try:
        payload = json.dumps(event, ensure_ascii=False, separators=(",", ":"))
    except TypeError:
        payload = repr(event)
    logger.log(level, "event=%s", payload)


REDACTED_HEADER_NAMES = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-api-key",
}
MAX_HEADER_VALUE_CHARS = 1000
TELEMETRY_DB_PATH = Path(
    os.getenv("COAUTHORS_TELEMETRY_DB_PATH", str(DATA_DIR / "coauthors_telemetry.sqlite"))
).expanduser().resolve()
TELEMETRY_BUSY_TIMEOUT_MS = int(os.getenv("COAUTHORS_TELEMETRY_BUSY_TIMEOUT_MS", "30000"))

COAUTHORS_CACHE_DB_PATH = Path(
    os.getenv("COAUTHORS_CACHE_DB_PATH", str(DATA_DIR / "coauthors_cache.sqlite"))
).expanduser().resolve()
COAUTHORS_CACHE_BUSY_TIMEOUT_MS = int(os.getenv("COAUTHORS_CACHE_BUSY_TIMEOUT_MS", "30000"))
COAUTHORS_CACHE_MAX_JSON_BYTES = max(int(os.getenv("COAUTHORS_CACHE_MAX_JSON_BYTES", "300000")), 10000)


def _sanitize_headers(request: Request) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in request.headers.items():
        key_l = key.lower()
        if key_l in REDACTED_HEADER_NAMES:
            sanitized[key_l] = "***redacted***"
        else:
            sanitized[key_l] = value[:MAX_HEADER_VALUE_CHARS]
    return sanitized


@dataclass(slots=True)
class TelemetryStore:
    db_path: Path
    busy_timeout_ms: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    _conn: sqlite3.Connection | None = field(default=None, init=False, repr=False)

    def _connect_locked(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=max(self.busy_timeout_ms / 1000.0, 1.0),
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.Error:
            # WAL may be unavailable depending on filesystem; still usable without it.
            pass
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        conn.execute("PRAGMA foreign_keys = ON;")

        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1');

            CREATE TABLE IF NOT EXISTS counters (
                key TEXT PRIMARY KEY,
                value INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                event_type TEXT NOT NULL,
                method TEXT,
                path TEXT,
                ip TEXT,
                ua TEXT,
                headers_json TEXT,
                payload_json TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
            CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, ts);
            CREATE INDEX IF NOT EXISTS idx_events_ip_ts ON events(ip, ts);
            """
        )
        conn.commit()

        self._conn = conn
        return conn

    def _close_conn_locked(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        finally:
            self._conn = None

    def close(self) -> None:
        with self.lock:
            self._close_conn_locked()

    def record_page_view(self, request: Request) -> int:
        ip = _get_client_ip(request)
        ua = _get_user_agent(request)
        headers = _sanitize_headers(request)
        now = _now_iso()

        with self.lock:
            conn = self._connect_locked()
            cur = conn.cursor()
            try:
                cur.execute("BEGIN IMMEDIATE;")
                cur.execute("INSERT OR IGNORE INTO counters(key, value) VALUES (?, 0);", ("page_views",))
                cur.execute("UPDATE counters SET value = value + 1 WHERE key = ?;", ("page_views",))
                cur.execute("SELECT value FROM counters WHERE key = ?;", ("page_views",))
                row = cur.fetchone()
                visit_count = int(row["value"]) if row else 0

                payload_json = json.dumps(
                    {"visit_count": visit_count, "url": str(request.url)},
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                headers_json = json.dumps(headers, ensure_ascii=False, separators=(",", ":"))
                cur.execute(
                    """
                    INSERT INTO events(ts, event_type, method, path, ip, ua, headers_json, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (now, "page_view", request.method, request.url.path, ip, ua, headers_json, payload_json),
                )
                conn.commit()
                return visit_count
            except Exception:
                conn.rollback()
                self._close_conn_locked()
                raise

    def record_event(self, event_type: str, request: Request, payload: dict[str, Any]) -> None:
        ip = _get_client_ip(request)
        ua = _get_user_agent(request)
        headers = _sanitize_headers(request)
        now = _now_iso()

        if "url" not in payload:
            payload = {**payload, "url": str(request.url)}

        try:
            payload_json = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        except TypeError:
            payload_json = json.dumps({"payload": repr(payload)}, ensure_ascii=False, separators=(",", ":"))
        headers_json = json.dumps(headers, ensure_ascii=False, separators=(",", ":"))

        with self.lock:
            conn = self._connect_locked()
            cur = conn.cursor()
            try:
                cur.execute(
                    """
                    INSERT INTO events(ts, event_type, method, path, ip, ua, headers_json, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                    """,
                    (now, event_type, request.method, request.url.path, ip, ua, headers_json, payload_json),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                self._close_conn_locked()
                raise


telemetry = TelemetryStore(db_path=TELEMETRY_DB_PATH, busy_timeout_ms=TELEMETRY_BUSY_TIMEOUT_MS)


@dataclass(slots=True)
class CacheStore:
    db_path: Path
    busy_timeout_ms: int
    lock: threading.Lock = field(default_factory=threading.Lock)
    _conn: sqlite3.Connection | None = field(default=None, init=False, repr=False)

    def _connect_locked(self) -> sqlite3.Connection:
        if self._conn is not None:
            return self._conn

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=max(self.busy_timeout_ms / 1000.0, 1.0),
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row
        conn.execute(f"PRAGMA busy_timeout = {self.busy_timeout_ms};")
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
        except sqlite3.Error:
            pass
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA temp_store = MEMORY;")

        cur = conn.cursor()
        cur.executescript(
            """
            CREATE TABLE IF NOT EXISTS meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            INSERT OR IGNORE INTO meta(key, value) VALUES ('schema_version', '1');

            CREATE TABLE IF NOT EXISTS author_resolve_cache (
                key TEXT PRIMARY KEY,
                db_size INTEGER NOT NULL,
                db_mtime_ns INTEGER NOT NULL,
                query TEXT NOT NULL,
                exact_base_match INTEGER NOT NULL,
                limit_val INTEGER,
                ids_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_author_resolve_db ON author_resolve_cache(db_mtime_ns, db_size);
            CREATE INDEX IF NOT EXISTS idx_author_resolve_query ON author_resolve_cache(query);

            CREATE TABLE IF NOT EXISTS pair_pubs_cache (
                key TEXT PRIMARY KEY,
                db_size INTEGER NOT NULL,
                db_mtime_ns INTEGER NOT NULL,
                limit_per_pair INTEGER,
                items_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_accessed TEXT NOT NULL,
                hit_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_pair_pubs_db ON pair_pubs_cache(db_mtime_ns, db_size);
            """
        )
        conn.commit()
        self._conn = conn
        return conn

    def _close_conn_locked(self) -> None:
        if self._conn is None:
            return
        try:
            self._conn.close()
        finally:
            self._conn = None

    def close(self) -> None:
        with self.lock:
            self._close_conn_locked()

    @staticmethod
    def _sha256(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get_author_ids(
        self,
        db_sig: DbSig,
        query: str,
        exact_base_match: bool,
        limit: int | None,
    ) -> list[int] | None:
        limit_val = -1 if limit is None else int(limit)
        key = self._sha256(
            f"author_ids|{db_sig.size}|{db_sig.mtime_ns}|{int(exact_base_match)}|{limit_val}|{query}"
        )
        now = _now_iso()

        with self.lock:
            conn = self._connect_locked()
            cur = conn.cursor()
            cur.execute("SELECT ids_json FROM author_resolve_cache WHERE key = ?;", (key,))
            row = cur.fetchone()
            if row is None:
                return None

            cur.execute(
                """
                UPDATE author_resolve_cache
                SET last_accessed = ?, hit_count = hit_count + 1
                WHERE key = ?;
                """,
                (now, key),
            )
            conn.commit()
            try:
                ids = json.loads(row["ids_json"])
            except Exception:
                return None
            if not isinstance(ids, list):
                return None
            out: list[int] = []
            for item in ids:
                if isinstance(item, int):
                    out.append(item)
            return out

    def put_author_ids(
        self,
        db_sig: DbSig,
        query: str,
        exact_base_match: bool,
        limit: int | None,
        ids: list[int],
    ) -> None:
        limit_val = -1 if limit is None else int(limit)
        key = self._sha256(
            f"author_ids|{db_sig.size}|{db_sig.mtime_ns}|{int(exact_base_match)}|{limit_val}|{query}"
        )
        now = _now_iso()
        ids_json = json.dumps(ids, ensure_ascii=False, separators=(",", ":"))
        if len(ids_json.encode("utf-8")) > COAUTHORS_CACHE_MAX_JSON_BYTES:
            return

        with self.lock:
            conn = self._connect_locked()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO author_resolve_cache(
                    key, db_size, db_mtime_ns, query, exact_base_match, limit_val,
                    ids_json, created_at, last_accessed, hit_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(key) DO UPDATE SET
                    ids_json = excluded.ids_json,
                    last_accessed = excluded.last_accessed;
                """,
                (
                    key,
                    db_sig.size,
                    db_sig.mtime_ns,
                    query,
                    int(exact_base_match),
                    None if limit is None else int(limit),
                    ids_json,
                    now,
                    now,
                ),
            )
            conn.commit()

    @staticmethod
    def _canonical_ids(ids: list[int]) -> str:
        # Canonical string for id sets, used only as part of a hash key.
        uniq = sorted({int(x) for x in ids})
        return ",".join(str(x) for x in uniq)

    def get_pair_items(
        self,
        db_sig: DbSig,
        left_ids: list[int],
        right_ids: list[int],
        limit_per_pair: int | None,
        year_min: int | None = None,
    ) -> list[dict[str, Any]] | None:
        left_key = self._canonical_ids(left_ids)
        right_key = self._canonical_ids(right_ids)
        a, b = (left_key, right_key) if left_key <= right_key else (right_key, left_key)
        limit_val = -1 if limit_per_pair is None else int(limit_per_pair)
        ym = -1 if year_min is None else int(year_min)
        key = self._sha256(f"pair_items|{db_sig.size}|{db_sig.mtime_ns}|{limit_val}|{ym}|{a}|{b}")
        now = _now_iso()

        with self.lock:
            conn = self._connect_locked()
            cur = conn.cursor()
            cur.execute("SELECT items_json FROM pair_pubs_cache WHERE key = ?;", (key,))
            row = cur.fetchone()
            if row is None:
                return None

            cur.execute(
                """
                UPDATE pair_pubs_cache
                SET last_accessed = ?, hit_count = hit_count + 1
                WHERE key = ?;
                """,
                (now, key),
            )
            conn.commit()
            try:
                items = json.loads(row["items_json"])
            except Exception:
                return None
            if not isinstance(items, list):
                return None
            out: list[dict[str, Any]] = []
            for it in items:
                if isinstance(it, dict):
                    out.append(it)
            return out

    def put_pair_items(
        self,
        db_sig: DbSig,
        left_ids: list[int],
        right_ids: list[int],
        limit_per_pair: int | None,
        items: list[dict[str, Any]],
        year_min: int | None = None,
    ) -> None:
        left_key = self._canonical_ids(left_ids)
        right_key = self._canonical_ids(right_ids)
        a, b = (left_key, right_key) if left_key <= right_key else (right_key, left_key)
        limit_val = -1 if limit_per_pair is None else int(limit_per_pair)
        ym = -1 if year_min is None else int(year_min)
        key = self._sha256(f"pair_items|{db_sig.size}|{db_sig.mtime_ns}|{limit_val}|{ym}|{a}|{b}")
        now = _now_iso()

        items_json = json.dumps(items, ensure_ascii=False, separators=(",", ":"))
        if len(items_json.encode("utf-8")) > COAUTHORS_CACHE_MAX_JSON_BYTES:
            return

        with self.lock:
            conn = self._connect_locked()
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO pair_pubs_cache(
                    key, db_size, db_mtime_ns, limit_per_pair, items_json, created_at, last_accessed, hit_count
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
                ON CONFLICT(key) DO UPDATE SET
                    items_json = excluded.items_json,
                    last_accessed = excluded.last_accessed;
                """,
                (
                    key,
                    db_sig.size,
                    db_sig.mtime_ns,
                    None if limit_per_pair is None else int(limit_per_pair),
                    items_json,
                    now,
                    now,
                ),
            )
            conn.commit()


cache_store = CacheStore(db_path=COAUTHORS_CACHE_DB_PATH, busy_timeout_ms=COAUTHORS_CACHE_BUSY_TIMEOUT_MS)


def _record_page_view(request: Request) -> int:
    try:
        return telemetry.record_page_view(request)
    except Exception:
        logger.exception("Failed to persist page view telemetry.")
        return _increment_page_views_fallback()


def _record_telemetry_event(
    event_type: str,
    request: Request,
    payload: dict[str, Any],
) -> None:
    try:
        telemetry.record_event(event_type, request, payload)
    except Exception:
        logger.exception("Failed to persist telemetry event.")


def _resolve_author_ids_cached(
    conn: sqlite3.Connection,
    db_sig: DbSig,
    name_query: str,
    limit: int | None,
    exact_base_match: bool,
) -> list[int]:
    normalized = _normalize(name_query)
    cached = cache_store.get_author_ids(
        db_sig=db_sig,
        query=normalized,
        exact_base_match=exact_base_match,
        limit=limit,
    )
    if cached is not None:
        return cached

    ids = _resolve_author_ids(conn, normalized, limit=limit, exact_base_match=exact_base_match)
    try:
        cache_store.put_author_ids(
            db_sig=db_sig,
            query=normalized,
            exact_base_match=exact_base_match,
            limit=limit,
            ids=ids,
        )
    except Exception:
        logger.exception("Failed to persist author id cache.")
    return ids


class StartRequest(BaseModel):
    mode: Literal["fullmeta"] = "fullmeta"
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
    year_min: int | None = Field(default=None, ge=1900, le=2100)


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


def _get_db_sig() -> DbSig:
    try:
        st = DB_PATH.stat()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Database file is not available.")
    except OSError as exc:
        raise HTTPException(status_code=503, detail=f"Cannot stat database file: {exc}") from exc

    mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))
    return DbSig(path=str(DB_PATH), size=st.st_size, mtime_ns=mtime_ns)


def _detect_data_date(sig: DbSig | None = None) -> str:
    override = os.getenv("DATA_DATE", "").strip()
    if override:
        return override

    mtime_ns: int
    if sig is not None:
        mtime_ns = sig.mtime_ns
    else:
        try:
            st = DB_PATH.stat()
        except OSError:
            return "unknown"
        mtime_ns = getattr(st, "st_mtime_ns", int(st.st_mtime * 1_000_000_000))

    ts = datetime.fromtimestamp(mtime_ns / 1_000_000_000, tz=timezone.utc)
    return ts.strftime("%Y-%m-%d")


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
    version=APP_VERSION,
)

manager = PipelineManager()
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("shutdown")
def _shutdown() -> None:
    telemetry.close()
    cache_store.close()


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    visit_count = _record_page_view(request)
    _log_event(
        {
            "type": "page_view",
            "path": "/",
            "ip": _get_client_ip(request),
            "ua": _get_user_agent(request),
            "visit_count": visit_count,
        }
    )
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "visit_count": visit_count,
        },
    )


@app.get("/bootstrap", response_class=HTMLResponse)
def bootstrap_console(request: Request, _user: str = Depends(_verify_bootstrap_auth)) -> HTMLResponse:
    visit_count = _record_page_view(request)
    _log_event(
        {
            "type": "page_view",
            "path": "/bootstrap",
            "ip": _get_client_ip(request),
            "ua": _get_user_agent(request),
            "visit_count": visit_count,
        }
    )
    return templates.TemplateResponse(
        "bootstrap.html",
        {
            "request": request,
            "app_version": APP_VERSION,
            "visit_count": visit_count,
            "default_mode": DEFAULT_MODE,
            "default_xml_gz_url": DEFAULT_XML_GZ_URL,
            "default_dtd_url": DEFAULT_DTD_URL,
            "default_batch_size": DEFAULT_BATCH_SIZE,
            "default_progress_every": DEFAULT_PROGRESS_EVERY,
            "data_dir": str(DATA_DIR),
        },
    )


@app.get("/api/health")
def api_health(response: Response) -> dict[str, Any]:
    sig = _get_db_sig()
    now = time.time()

    with _health_cache.lock:
        if _health_cache.sig == sig and now < _health_cache.expires_at:
            response.headers["X-CoAuthors-Cache"] = "health-hit"
            if _health_cache.ok:
                return {"status": "ok"}
            raise HTTPException(
                status_code=_health_cache.status_code,
                detail=_health_cache.detail or "Health check failed.",
            )

        try:
            conn = _get_connection()
            try:
                _ensure_fullmeta_schema(conn)
            finally:
                conn.close()

            _health_cache.ok = True
            _health_cache.status_code = 200
            _health_cache.detail = None
        except HTTPException as exc:
            _health_cache.ok = False
            _health_cache.status_code = exc.status_code
            _health_cache.detail = str(exc.detail) if exc.detail is not None else None

        _health_cache.sig = sig
        _health_cache.expires_at = now + HEALTH_CACHE_TTL_SEC

        response.headers["X-CoAuthors-Cache"] = "health-miss"
        if _health_cache.ok:
            return {"status": "ok"}
        raise HTTPException(
            status_code=_health_cache.status_code,
            detail=_health_cache.detail or "Health check failed.",
        )


@app.get("/api/stats")
def api_stats(response: Response) -> dict[str, Any]:
    sig = _get_db_sig()

    with _stats_cache.lock:
        if _stats_cache.sig == sig and _stats_cache.value is not None:
            response.headers["X-CoAuthors-Cache"] = "stats-hit"
            return _stats_cache.value

        conn = _get_connection()
        try:
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) AS cnt FROM publications;")
            pub_count = cur.fetchone()["cnt"]
            cur.execute("SELECT COUNT(*) AS cnt FROM authors;")
            author_count = cur.fetchone()["cnt"]
            value = {
                "publications": pub_count,
                "authors": author_count,
                "data_source": "DBLP",
                "data_date": _detect_data_date(sig),
            }
        finally:
            conn.close()

        _stats_cache.sig = sig
        _stats_cache.value = value
        response.headers["X-CoAuthors-Cache"] = "stats-miss"
        return value


@app.get("/api/pc-members")
def api_pc_members() -> dict[str, Any]:
    return {"members": PC_MEMBERS, "count": len(PC_MEMBERS)}


@app.post("/api/coauthors/pairs")
def api_coauthors_pairs(payload: CoauthoredPairsRequest, request: Request) -> dict[str, Any]:
    acquired = _query_semaphore.acquire(timeout=QUERY_ACQUIRE_TIMEOUT_SEC)
    if not acquired:
        _log_event(
            {
                "type": "query_rejected",
                "reason": "too_many_concurrent_queries",
                "ip": _get_client_ip(request),
                "ua": _get_user_agent(request),
            },
            level=logging.WARNING,
        )
        _record_telemetry_event(
            "query_rejected",
            request,
            {"reason": "too_many_concurrent_queries"},
        )
        raise HTTPException(
            status_code=429,
            detail="Too many concurrent queries. Please retry in a moment.",
        )

    ip = _get_client_ip(request)
    ua = _get_user_agent(request)
    started_at = time.time()
    db_sig = _get_db_sig()

    left_entries = _sanitize_author_entries(payload.left)
    right_entries = _sanitize_author_entries(payload.right)
    if not left_entries or not right_entries:
        _log_event(
            {
                "type": "query_rejected",
                "reason": "missing_authors",
                "ip": ip,
                "ua": ua,
                "left": left_entries,
                "right": right_entries,
            },
            level=logging.WARNING,
        )
        _record_telemetry_event(
            "query_rejected",
            request,
            {
                "reason": "missing_authors",
                "left": left_entries,
                "right": right_entries,
            },
        )
        raise HTTPException(status_code=400, detail="Both left and right author lists are required.")

    if len(left_entries) > MAX_ENTRIES_PER_SIDE or len(right_entries) > MAX_ENTRIES_PER_SIDE:
        _log_event(
            {
                "type": "query_rejected",
                "reason": "too_many_authors",
                "ip": ip,
                "ua": ua,
                "left_n": len(left_entries),
                "right_n": len(right_entries),
                "max_per_side": MAX_ENTRIES_PER_SIDE,
            },
            level=logging.WARNING,
        )
        _record_telemetry_event(
            "query_rejected",
            request,
            {
                "reason": "too_many_authors",
                "left_n": len(left_entries),
                "right_n": len(right_entries),
                "max_per_side": MAX_ENTRIES_PER_SIDE,
            },
        )
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
    year_min = payload.year_min

    conn = _get_connection()
    try:
        _ensure_fullmeta_schema(conn)

        left_ids: dict[str, list[int]] = {}
        right_ids: dict[str, list[int]] = {}

        for entry in left_entries:
            left_ids[entry] = _resolve_author_ids_cached(
                conn, db_sig, entry, limit=author_limit, exact_base_match=payload.exact_base_match
            )

        for entry in right_entries:
            right_ids[entry] = _resolve_author_ids_cached(
                conn, db_sig, entry, limit=author_limit, exact_base_match=payload.exact_base_match
            )

        matrix: dict[str, dict[str, int]] = {left: {} for left in left_entries}
        pair_pubs: list[dict[str, Any]] = []
        cur = conn.cursor()
        local_pair_cache: dict[str, list[dict[str, Any]]] = {}

        for left_entry, left_author_ids in left_ids.items():
            for right_entry, right_author_ids in right_ids.items():
                if not left_author_ids or not right_author_ids:
                    items: list[dict[str, Any]] = []
                else:
                    # Cache by resolved author id sets (unordered for hit rate), plus limit_per_pair and year_min.
                    # Also keep a per-request local dict to avoid re-querying the cache DB.
                    pair_key = CacheStore._sha256(
                        f"pair_items|{db_sig.size}|{db_sig.mtime_ns}|"
                        f"{-1 if limit_per_pair is None else int(limit_per_pair)}|"
                        f"{-1 if year_min is None else int(year_min)}|"
                        f"{CacheStore._canonical_ids(left_author_ids)}|{CacheStore._canonical_ids(right_author_ids)}"
                    )
                    cached_items = local_pair_cache.get(pair_key)
                    if cached_items is None:
                        cached_items = cache_store.get_pair_items(
                            db_sig=db_sig,
                            left_ids=left_author_ids,
                            right_ids=right_author_ids,
                            limit_per_pair=limit_per_pair,
                            year_min=year_min,
                        )
                        if cached_items is not None:
                            local_pair_cache[pair_key] = cached_items

                    if cached_items is not None:
                        items = cached_items
                    else:
                        limit_sql = "" if limit_per_pair is None else "LIMIT ?"
                        year_filter_sql = "" if year_min is None else "AND p.year >= ?"
                        params: tuple[Any, ...] = (*left_author_ids, *right_author_ids)
                        if year_min is not None:
                            params = (*params, year_min)
                        if limit_per_pair is not None:
                            params = (*params, limit_per_pair)

                        order_sql = "ORDER BY (p.year IS NULL) ASC, p.year DESC, p.title ASC"
                        cur.execute(
                            f"""
                            SELECT DISTINCT p.title, p.year, p.venue, p.pub_type
                            FROM pub_authors pa1
                            JOIN pub_authors pa2 ON pa1.pub_id = pa2.pub_id
                            JOIN publications p ON p.id = pa1.pub_id
                            WHERE pa1.author_id IN ({_placeholders(left_author_ids)})
                              AND pa2.author_id IN ({_placeholders(right_author_ids)})
                            {year_filter_sql}
                            {order_sql}
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
                        try:
                            cache_store.put_pair_items(
                                db_sig=db_sig,
                                left_ids=left_author_ids,
                                right_ids=right_author_ids,
                                limit_per_pair=limit_per_pair,
                                items=items,
                                year_min=year_min,
                            )
                            local_pair_cache[pair_key] = items
                        except Exception:
                            logger.exception("Failed to persist pair pubs cache.")

                matrix[left_entry][right_entry] = len(items)
                pair_pubs.append(
                    {
                        "left": left_entry,
                        "right": right_entry,
                        "count": len(items),
                        "items": items,
                    }
                )

        result = {
            "mode": "fullmeta",
            "limit_per_pair": limit_per_pair,
            "exact_base_match": payload.exact_base_match,
            "left_authors": left_entries,
            "right_authors": right_entries,
            "matrix": matrix,
            "pair_pubs": pair_pubs,
            "pair_count": len(pair_pubs),
        }
        coauthored_pairs = sum(1 for pair in pair_pubs if (pair.get("count") or 0) > 0)
        telemetry_payload = {
            "left": left_entries,
            "right": right_entries,
            "exact_base_match": payload.exact_base_match,
            "limit_per_pair": limit_per_pair,
            "author_limit": author_limit,
            "pair_count": len(pair_pubs),
            "coauthored_pair_count": coauthored_pairs,
            "elapsed_ms": int((time.time() - started_at) * 1000),
        }
        _log_event(
            {
                "type": "query",
                "ip": ip,
                "ua": ua,
                **telemetry_payload,
            }
        )
        _record_telemetry_event("query", request, telemetry_payload)
        return result
    finally:
        conn.close()
        if acquired:
            _query_semaphore.release()


@app.get("/api/config")
def api_config(_user: str = Depends(_verify_bootstrap_auth)) -> dict[str, Any]:
    return {
        "default_mode": DEFAULT_MODE,
        "default_xml_gz_url": DEFAULT_XML_GZ_URL,
        "default_dtd_url": DEFAULT_DTD_URL,
        "default_batch_size": DEFAULT_BATCH_SIZE,
        "default_progress_every": DEFAULT_PROGRESS_EVERY,
        "data_dir": str(DATA_DIR),
    }


@app.get("/api/state")
def api_state(_user: str = Depends(_verify_bootstrap_auth)) -> dict[str, Any]:
    return manager.snapshot()


@app.get("/api/files")
def api_files(_user: str = Depends(_verify_bootstrap_auth)) -> dict[str, Any]:
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
def api_start(req: StartRequest, _user: str = Depends(_verify_bootstrap_auth)) -> dict[str, Any]:
    return manager.start(req)


@app.post("/api/stop")
def api_stop(_user: str = Depends(_verify_bootstrap_auth)) -> dict[str, Any]:
    return manager.stop()


@app.post("/api/reset")
def api_reset(_user: str = Depends(_verify_bootstrap_auth)) -> dict[str, Any]:
    return manager.reset()
