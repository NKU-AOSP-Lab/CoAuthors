from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


class RuntimeStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_lock = threading.Lock()
        self._initialized = False
        self._ensure_initialized()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        with self._init_lock:
            if self._initialized:
                return
            conn = self._connect()
            try:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA synchronous=NORMAL")
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS runtime_counters (
                        name TEXT PRIMARY KEY,
                        value INTEGER NOT NULL DEFAULT 0,
                        updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS page_visits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        route TEXT NOT NULL,
                        client_ip TEXT,
                        user_agent TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS query_cache (
                        cache_key TEXT PRIMARY KEY,
                        response_json TEXT NOT NULL,
                        created_at TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at TEXT NOT NULL DEFAULT (datetime('now')),
                        hit_count INTEGER NOT NULL DEFAULT 0,
                        last_hit_at TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS query_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        event_type TEXT NOT NULL,
                        query_hash TEXT,
                        left_count INTEGER NOT NULL DEFAULT 0,
                        right_count INTEGER NOT NULL DEFAULT 0,
                        total_pairs INTEGER NOT NULL DEFAULT 0,
                        cache_hit INTEGER NOT NULL DEFAULT 0,
                        success INTEGER NOT NULL DEFAULT 1,
                        duration_ms INTEGER,
                        error_message TEXT,
                        extra_json TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS event_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        level TEXT NOT NULL,
                        message TEXT NOT NULL,
                        detail_json TEXT,
                        created_at TEXT NOT NULL DEFAULT (datetime('now'))
                    )
                    """
                )
                conn.commit()
                self._initialized = True
            finally:
                conn.close()

    def increment_counter(self, name: str, delta: int = 1) -> int:
        self._ensure_initialized()
        conn = self._connect()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO runtime_counters (name, value, updated_at)
                VALUES (?, ?, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    value = runtime_counters.value + excluded.value,
                    updated_at = datetime('now')
                """,
                (name, delta),
            )
            cur.execute("SELECT value FROM runtime_counters WHERE name = ?", (name,))
            row = cur.fetchone()
            conn.commit()
            return int(row["value"]) if row else 0
        finally:
            conn.close()

    def get_counter(self, name: str) -> int:
        self._ensure_initialized()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT value FROM runtime_counters WHERE name = ?",
                (name,),
            ).fetchone()
            return int(row["value"]) if row else 0
        finally:
            conn.close()

    def record_page_visit(self, route: str, client_ip: str | None, user_agent: str | None) -> int:
        self._ensure_initialized()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO page_visits (route, client_ip, user_agent)
                VALUES (?, ?, ?)
                """,
                (route, client_ip, user_agent),
            )
            conn.execute(
                """
                INSERT INTO runtime_counters (name, value, updated_at)
                VALUES ('visit_count', 1, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    value = runtime_counters.value + 1,
                    updated_at = datetime('now')
                """
            )
            row = conn.execute(
                "SELECT value FROM runtime_counters WHERE name = 'visit_count'"
            ).fetchone()
            conn.commit()
            return int(row["value"]) if row else 0
        finally:
            conn.close()

    def cache_get(self, cache_key: str) -> dict[str, Any] | None:
        self._ensure_initialized()
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT response_json FROM query_cache WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE query_cache
                SET hit_count = hit_count + 1, last_hit_at = datetime('now')
                WHERE cache_key = ?
                """,
                (cache_key,),
            )
            conn.execute(
                """
                INSERT INTO runtime_counters (name, value, updated_at)
                VALUES ('cache_hit_count', 1, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    value = runtime_counters.value + 1,
                    updated_at = datetime('now')
                """
            )
            conn.commit()
            return json.loads(str(row["response_json"]))
        finally:
            conn.close()

    def cache_put(self, cache_key: str, response_data: dict[str, Any]) -> None:
        self._ensure_initialized()
        conn = self._connect()
        try:
            payload = json.dumps(response_data, ensure_ascii=False, separators=(",", ":"))
            conn.execute(
                """
                INSERT INTO query_cache (cache_key, response_json, created_at, updated_at)
                VALUES (?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_json = excluded.response_json,
                    updated_at = datetime('now')
                """,
                (cache_key, payload),
            )
            conn.execute(
                """
                INSERT INTO runtime_counters (name, value, updated_at)
                VALUES ('cache_write_count', 1, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    value = runtime_counters.value + 1,
                    updated_at = datetime('now')
                """
            )
            conn.commit()
        finally:
            conn.close()

    def record_query_event(
        self,
        *,
        event_type: str,
        query_hash: str | None,
        left_count: int,
        right_count: int,
        total_pairs: int,
        cache_hit: bool,
        success: bool,
        duration_ms: int | None,
        error_message: str | None,
        extra: dict[str, Any] | None,
    ) -> None:
        self._ensure_initialized()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO query_events (
                    event_type,
                    query_hash,
                    left_count,
                    right_count,
                    total_pairs,
                    cache_hit,
                    success,
                    duration_ms,
                    error_message,
                    extra_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_type,
                    query_hash,
                    int(left_count),
                    int(right_count),
                    int(total_pairs),
                    1 if cache_hit else 0,
                    1 if success else 0,
                    int(duration_ms) if duration_ms is not None else None,
                    error_message,
                    json.dumps(extra or {}, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.execute(
                """
                INSERT INTO runtime_counters (name, value, updated_at)
                VALUES ('query_event_count', 1, datetime('now'))
                ON CONFLICT(name) DO UPDATE SET
                    value = runtime_counters.value + 1,
                    updated_at = datetime('now')
                """
            )
            conn.commit()
        finally:
            conn.close()

    def log_event(self, level: str, message: str, detail: dict[str, Any] | None = None) -> None:
        self._ensure_initialized()
        conn = self._connect()
        try:
            conn.execute(
                """
                INSERT INTO event_logs (level, message, detail_json)
                VALUES (?, ?, ?)
                """,
                (
                    level.upper(),
                    message,
                    json.dumps(detail or {}, ensure_ascii=False, separators=(",", ":")),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    def stats(self) -> dict[str, Any]:
        self._ensure_initialized()
        conn = self._connect()
        try:
            counters = {
                row["name"]: int(row["value"])
                for row in conn.execute("SELECT name, value FROM runtime_counters")
            }
            cache_size = conn.execute("SELECT COUNT(1) AS c FROM query_cache").fetchone()
            query_events = conn.execute("SELECT COUNT(1) AS c FROM query_events").fetchone()
            page_visits = conn.execute("SELECT COUNT(1) AS c FROM page_visits").fetchone()
            return {
                "counters": counters,
                "cache_entries": int(cache_size["c"]) if cache_size else 0,
                "query_events": int(query_events["c"]) if query_events else 0,
                "page_visits": int(page_visits["c"]) if page_visits else 0,
            }
        finally:
            conn.close()
