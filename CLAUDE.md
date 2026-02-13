# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

```bash
# Install dependencies
python -m pip install -r requirements.txt

# Run locally
python -m uvicorn app:app --host 0.0.0.0 --port 8090

# Run via Docker
docker compose up -d --build
```

UI routes: `/` (user query), `/console` (advanced query), `/bootstrap` (pipeline console).

No automated test suite exists. If adding tests, use `pytest` + FastAPI `TestClient` under `tests/test_*.py`.

## Architecture

**Backend** is two Python files with a clear separation of concerns:
- `app.py` — FastAPI application: HTTP routes, Jinja2 templates, query logic, caching, telemetry, concurrency control
- `builder.py` — DBLP pipeline: download XML.GZ, decompress, parse with lxml iterparse, build SQLite database

**Frontend** is vanilla JS + CSS with Jinja2 templates (no framework):
- `static/query_app.js` — shared logic for both `/` and `/console` pages (API calls, rendering, i18n, theme switching)
- `static/bootstrap_app.js` — bootstrap console logic (start/stop/reset, polling, live logs)
- Templates receive config via Jinja2 context; JS reads it from DOM and localStorage

**Three separate SQLite databases** (all under `DATA_DIR`, default `/data`):
- `dblp.sqlite` — main DBLP data (publications, authors, pub_authors, FTS indexes)
- `coauthors_cache.sqlite` — query result cache (author resolution + pair publications), keyed by DB file signature (size + mtime)
- `coauthors_telemetry.sqlite` — request event logging and counters

## Key Architectural Patterns

**Query flow** (`POST /api/coauthors/pairs`): BoundedSemaphore acquire → parse/sanitize author names (strip org suffixes) → resolve author IDs via FTS/LIKE with cache lookup → query coauthorship pairs via SQL JOIN on `pub_authors` with cache lookup → log telemetry → return JSON → semaphore release.

**Bootstrap flow** (`POST /api/start`): `PipelineManager.start()` spawns a background thread → `builder.run_pipeline()` executes stages (download DTD → download XML.GZ → decompress → parse XML + batch-insert into SQLite) → progress/log callbacks update shared state → frontend polls `/api/state` and `/api/files`.

**Concurrency**: Threading locks protect pipeline state mutations. A `BoundedSemaphore` throttles concurrent query execution (configurable via `COAUTHORS_MAX_CONCURRENT_QUERIES`).

**Cache invalidation**: Caches use a `DbSig` (db file size + mtime_ns) so all cached entries auto-invalidate when the database file changes (e.g., after a rebuild).

## Conventions

- **Naming**: `snake_case` for functions/variables, `PascalCase` for Pydantic models and dataclasses, `UPPER_SNAKE_CASE` for constants. Private functions use leading underscore.
- **Commits**: Conventional Commits format (`feat:`, `fix:`, `docs:`, `refactor:`).
- **Separation**: I/O and parsing logic belongs in `builder.py`; HTTP, templating, and query logic belongs in `app.py`.
- **Config**: All configuration via `os.getenv()` with defaults. See README.md for the full environment variable reference.
- **Runtime data**: Never commit files under `DATA_DIR` (`*.sqlite`, `*.xml*`, `*.dtd`, logs).

## Important Notes

- Query pages require **fullmeta** build mode. Building with `base` mode produces a schema missing `year`/`venue`/`pub_type`/`raw_xml` columns, and `/api/health` will report schema incompatibility.
- The app uses Python 3.10+ union syntax (`X | None`) and dataclasses with `frozen=True`/`slots=True`.
- Frontend i18n uses `data-i18n` attributes on DOM elements with a `t(key)` translation function; themes switch via a `data-style` attribute on the body.
