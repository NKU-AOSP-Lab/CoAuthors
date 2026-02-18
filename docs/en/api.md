# API Reference

## Frontend Service Endpoints

### `GET /`

Returns the CoAuthors query page.

### `GET /api/runtime/stats`

Returns runtime statistics.

### `POST /api/runtime/cache/get`

Request body:

```json
{ "key": "pairs:v1:abcd1234" }
```

### `POST /api/runtime/cache/put`

Request body:

```json
{ "key": "pairs:v1:abcd1234", "data": { "left_authors": [], "right_authors": [] } }
```

### `POST /api/runtime/query/event`

Records query hit/miss, duration, and errors.

## Required DblpService Endpoints

- `GET /api/health`
- `GET /api/stats`
- `GET /api/pc-members`
- `POST /api/coauthors/pairs`
