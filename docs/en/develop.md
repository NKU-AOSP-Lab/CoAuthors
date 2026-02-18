# Development Guide

## 1. Architecture and Boundaries

CoAuthors is a query frontend. It does not build DBLP data or run coauthorship computation itself. Responsibilities are split into:

1. **HTTP/UI layer** (`app.py`, `templates/`, `static/`)
   - Renders `GET /`.
   - Exposes local runtime APIs (cache + telemetry).
2. **Runtime persistence layer** (`runtime_store.py`)
   - Stores visits, cache entries, query events, and logs in SQLite.
3. **Backend integration layer** (`static/query_app.js` + `API_BASE_URL`)
   - Forwards coauthor queries to DblpService `POST /api/coauthors/pairs`.

Author resolution, coauthor pair computation, and DB constraints are implemented in `CoAuthors/DblpService`.

## 2. End-to-End Request Flow

### 2.1 Page Visit Flow

1. Browser requests `GET /`.
2. `app.py` calls `RuntimeStore.record_page_visit()` to write `page_visits` and increment `visit_count`.
3. Server renders `index.html` with:
   - `app_version`
   - `visit_count`
   - `api_base` (from `API_BASE_URL`)

### 2.2 Coauthor Query Flow (with cache)

1. Frontend reads left/right inputs and splits lines (`parseLines`).
2. Each author entry is normalized (`sanitizeAuthorEntries`):
   - trim and collapse whitespace;
   - strip organization suffixes (for example `Name || Org`, `Name (Org)`);
   - de-duplicate while preserving first occurrence order.
3. Build payload (`left/right/exact_base_match/limit_per_pair/author_limit/year_min`).
4. Build cache key: `pairs:v1:<fnv1a32(json_payload)>`.
5. Read local runtime cache via `POST /api/runtime/cache/get`.
6. On cache hit, render directly; on miss, call DblpService `POST /api/coauthors/pairs`.
7. Asynchronously write successful remote result to cache via `POST /api/runtime/cache/put`.
8. Report telemetry via `POST /api/runtime/query/event` for both success and failure.

Important: cache write and telemetry reporting are best-effort and non-blocking. Failures are swallowed and do not fail the main query path.

## 3. Cache Design (Detailed)

### 3.1 Cache Layers

- **L1 (frontend memory state)**: in-page render state (for example selected pair state).
- **L2 (SQLite persistent cache)**: `query_cache`, effective across requests and page refreshes.

### 3.2 L2 Key/Value

- Key: `cache_key` (current namespace `pairs:v1:*`).
- Value: full JSON response (`response_json`).
- Hit metadata: `hit_count`, `last_hit_at`.

### 3.3 Invalidation Behavior

- There is currently **no TTL**, **no LRU**, and **no capacity limit**.
- Same key overwrites old value (`ON CONFLICT DO UPDATE`).
- If underlying DBLP data changes, cache is not auto-invalidated. You must clear cache manually or bump key namespace (for example `pairs:v2`).

## 4. Concurrency Model and Overload Behavior (Wait / Reject / Degrade)

| Scenario | Constraint | Behavior when exceeded | Result |
|---|---|---|---|
| Frontend author count | max `50` per side | reject in browser (no request sent) | UI error |
| DblpService author count | max `MAX_ENTRIES_PER_SIDE` (default 50, hard-capped at 50) | immediate reject | `400` |
| `limit_per_pair` | clamped to `[1, MAX_LIMIT]` (default MAX_LIMIT=200) | no reject, auto-clamp | `200` |
| `author_limit` | clamped to max `MAX_AUTHOR_RESOLVE` (default 800) | no reject, auto-clamp | `200` |
| Runtime SQLite write contention | `sqlite timeout=30s` + `WAL` | wait for lock first | timeout raises exception (typically `500`) |
| DblpService DB lock contention | `PRAGMA busy_timeout=30000` | wait for lock first | timeout fails (commonly `500`; DB unavailable can be `503`) |
| Pipeline start while running | only one pipeline thread allowed | immediate reject | `409 Pipeline is already running` |
| Pipeline reset while running | reset forbidden during running | immediate reject | `409 Cannot reset while running` |
| Runtime cache read failure | none | degrade to direct backend query | request continues |
| Runtime cache write / telemetry failure | none | ignore failure | request continues |

Summary: request concurrency is mainly handled by **waiting on DB locks**; business limit violations are **immediate rejects**; runtime-observability failures are handled with **degradation**.

## 5. API Validation and Error Semantics

### 5.1 CoAuthors runtime APIs (`app.py`)

- `POST /api/runtime/cache/get`
  - `key`: length `1..256`
  - invalid input returns `422` via FastAPI/Pydantic
- `POST /api/runtime/cache/put`
  - `key`: length `1..256`
  - `data`: JSON object
  - blank key after trim returns `400`
- `POST /api/runtime/query/event`
  - `left_count/right_count`: `0..500`
  - `total_pairs`: `0..250000`
  - `duration_ms`: `0..86400000`
  - `error_message`: max length `1000`
  - out-of-range values return `422`

### 5.2 DblpService query API

- `POST /api/coauthors/pairs` requires both left and right lists non-empty; otherwise `400`.
- Missing database file or incomplete schema returns `503`.

## 6. Runtime Tables and Observability

`runtime_store.py` initializes:

- `runtime_counters`
- `page_visits`
- `query_cache`
- `query_events`
- `event_logs`

Recommended KPIs:

- query volume: `query_event_count`
- cache hits: `cache_hit_count`
- cache writes: `cache_write_count`
- cache size: row count of `query_cache`
- error ratio: `query_events.success=0` ratio

## 7. Extension Guidelines

- Keep business/query logic in DblpService; CoAuthors should stay orchestration + presentation only.
- Bump cache key namespace when cache semantics change (for example `pairs:v2`).
- Prefer appending telemetry fields in `query_events.extra_json` to avoid schema churn.
- For any new high-cost feature, define and document its overload strategy explicitly: wait, reject, or degrade.