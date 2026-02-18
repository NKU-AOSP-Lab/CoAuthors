<div align="center" style="display:flex;justify-content:center;align-items:center;gap:8px;">
  <img src="./static/coauthors-logo.svg" alt="CoAuthors Logo" width="34" />
  <strong>CoAuthors</strong>
</div>

<p align="center">DBLP co-authorship query frontend with runtime cache and telemetry.</p>

<p align="center">[<a href="./README.md"><strong>EN</strong></a>] | [<a href="./README.zh-CN.md"><strong>CN</strong></a>]</p>

<p align="center">
  <img src="https://img.shields.io/badge/version-1.0.0-1f7a8c" alt="version" />
  <img src="https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white" alt="python" />
  <img src="https://img.shields.io/badge/FastAPI-0.111%2B-009688?logo=fastapi&logoColor=white" alt="fastapi" />
  <img src="https://img.shields.io/badge/docs-MkDocs-526CFE?logo=materialformkdocs&logoColor=white" alt="docs" />
</p>

## Overview

CoAuthors is the web interface project for querying DBLP co-author relationships. It focuses on query UX, matrix rendering, and runtime observability, while delegating DBLP data services to `DblpService`.

## Core Capabilities

- Query and render co-author collaboration matrices.
- Call backend APIs for pairwise co-author statistics.
- Store runtime cache and telemetry data in SQLite.
- Provide runtime inspection APIs for frontend operation metrics.

## Local Run

```bash
cd CoAuthors
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8090
```

Run bundled backend service (optional but recommended for local integration):

```bash
cd CoAuthors/DblpService
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8091
```

Open:

- `http://localhost:8090/`
- `http://localhost:8091/bootstrap`

## Docker

```bash
cd CoAuthors
docker compose up -d --build
```

Default ports:

- `coauthors-frontend`: `8090`
- `coauthors-dblp-service`: `8091`

## Documentation

- English docs: https://coauthors.readthedocs.io/en/latest/
- Docs source (in repo): `docs/en/`, `docs/zh/`

Local preview:

```bash
cd CoAuthors
python -m pip install -r docs/requirements.txt
mkdocs serve
```


