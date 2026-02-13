# CoAuthors Bootstrap Console

A lightweight open-source project that combines:

1. Coauthorship query system
- `/` user-friendly query page
- `/console` advanced query page with tuning options

2. DBLP bootstrap console
- `/bootstrap` download `dblp.dtd` + `dblp.xml.gz`, decompress XML, and build SQLite

## Highlights

- Default UI style: `Campus Modern`
- Top-bar controls for both **style** and **language** (English/Chinese)
- Query inputs automatically strip organization suffixes like `Name (Org)`
- User page hides advanced controls (`limit_per_pair`, `author_limit`) by default
- Status cell includes service health, `DBLP` source, and data date
- Footer shows developer/maintainer, version, features, and license
- Fullmeta output includes `title/year/venue/pub_type`

Developer and Maintainer: **Nankai University AOSP Laboratory**
License: **MIT**

## Quick Start (Local)

```bash
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8090
```

Open:
- `http://localhost:8090/`
- `http://localhost:8090/console`
- `http://localhost:8090/bootstrap`

## Quick Start (Docker)

```bash
docker compose up -d --build
```

Open: `http://localhost:8090`

## Project Structure

```text
bootstrap_console/
  app.py                 # FastAPI app (query + bootstrap)
  builder.py             # download/decompress/build pipeline
  templates/
    index.html           # user query page
    console.html         # advanced query page
    bootstrap.html       # bootstrap page
  static/
    query_app.js
    query_styles.css
    bootstrap_app.js
    bootstrap_styles.css
  Dockerfile
  docker-compose.yml
  requirements.txt
  .gitignore
```

## APIs

Query APIs:
- `GET /api/health`
- `GET /api/stats`
- `POST /api/coauthors/pairs`

Bootstrap APIs:
- `GET /api/config`
- `GET /api/state`
- `GET /api/files`
- `POST /api/start`
- `POST /api/stop`
- `POST /api/reset`

## Environment Variables

Bootstrap:
- `DATA_DIR` (default: `/data`)
- `DBLP_XML_GZ_URL` (default: `https://dblp.org/xml/dblp.xml.gz`)
- `DBLP_DTD_URL` (default: `https://dblp.org/xml/dblp.dtd`)
- `DEFAULT_BUILD_MODE` (`base`/`fullmeta`, default: `fullmeta`)
- `BATCH_SIZE` (default: `1000`)
- `PROGRESS_EVERY` (default: `10000`)
- `MAX_LOG_LINES` (default: `1000`)

Query:
- `DB_PATH` (default: `${DATA_DIR}/dblp.sqlite`)
- `DB_BUSY_TIMEOUT_MS` (default: `30000`)
- `MAX_LIMIT` (default: `200`)
- `MAX_ENTRIES_PER_SIDE` (default: `120`)
- `MAX_AUTHOR_RESOLVE` (default: `800`)
- `DATA_DATE` (optional explicit data date shown in UI)

## Notes

- Query pages require fullmeta schema (`year/venue/pub_type/raw_xml` in `publications`).
- If you build with `base` mode only, `/api/health` for query pages reports schema incompatibility.


## Project Docs

- [CHANGELOG](./CHANGELOG.md)
- [LICENSE](./LICENSE)

