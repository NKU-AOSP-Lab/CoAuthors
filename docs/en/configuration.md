# Configuration

## Core Environment Variables

| Variable | Default | Description |
|---|---|---|
| `API_BASE_URL` | `http://localhost:8091` | Target DBLP API base URL |
| `COAUTHORS_DATA_DIR` | `${PROJECT_DIR}/data` | Runtime folder (cache/telemetry DB) |
| `COAUTHORS_RUNTIME_DB` | `${COAUTHORS_DATA_DIR}/runtime.sqlite` | Runtime SQLite path |

## Runtime Data

The runtime database stores:

- `page_visits`: page visit events
- `query_cache`: cached query responses
- `query_events`: query telemetry and duration
- `event_logs`: app-level logs

## Recommended Settings

- Pin `API_BASE_URL` to a stable backend endpoint
- Persist `runtime.sqlite` with a mounted volume
- Manage ports behind a reverse proxy in production
