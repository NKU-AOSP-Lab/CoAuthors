# Quick Start

## Local Run

```bash
cd CoAuthors
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8090
```

Open: `http://localhost:8090`

## Start Backend Dependency

CoAuthors requires a running `DblpService` instance:

```bash
cd CoAuthors/DblpService
python -m pip install -r requirements.txt
python -m uvicorn app:app --host 0.0.0.0 --port 8091
```

## Standalone Docker Deployment

```bash
cd CoAuthors
docker compose up -d --build
```

Default services:

- `coauthors-frontend`: `8090`
- `coauthors-dblp-service`: `8091`
