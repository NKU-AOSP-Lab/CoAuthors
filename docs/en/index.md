<p align="center">
  <img src="images/logo.svg" alt="CoAuthors Logo" width="56" style="vertical-align:middle;" />
  <span style="font-size:1.8rem;font-weight:700;vertical-align:middle;margin-left:8px;">CoAuthors Documentation</span>
</p>

CoAuthors is the DBLP co-authorship frontend. It focuses on user interaction, query orchestration, and runtime observability.

## What CoAuthors Handles

- UI rendering for co-authorship search
- Input normalization and request packaging
- Runtime cache read/write and query telemetry
- Backend integration with `DblpService`

## Runtime Characteristics

- Service entry: `GET /`
- Local runtime APIs:
  - `GET /api/runtime/stats`
  - `POST /api/runtime/cache/get`
  - `POST /api/runtime/cache/put`
  - `POST /api/runtime/query/event`
- Runtime storage: SQLite (`runtime.sqlite`)
- Cache behavior: payload-keyed persistence in `query_cache`

## Integration Topology

- Frontend endpoint: `http://localhost:8090`
- Backend target via `API_BASE_URL` (default `http://localhost:8091`)
- DBLP build/query lifecycle is served by `DblpService`

## Recommended Reader Path

1. [Quick Start](quickstart.md)
2. [Configuration](configuration.md)
3. [API Reference](api.md)
4. [Development Guide](develop.md)
5. [Operations](operations.md)
6. [Troubleshooting](troubleshooting.md)
7. [Changelog](changelog.md)

## Audience

- Engineers deploying a standalone co-author lookup frontend
- Teams integrating UI workflows with DBLP backend services
- Maintainers tracking runtime cache and telemetry behavior


