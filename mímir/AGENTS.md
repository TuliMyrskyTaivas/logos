# AGENTS.md

Guidelines for AI coding agents working in the Mímir service. Mímir is a
separate Python web service; read this file before making changes here.
It supplements the root-level `AGENTS.md` (the root SQLAlchemy / NumPy /
pandas rules apply).

## Overview

Mímir is a gateway to the Logos PostgreSQL database. It exposes financial
analytics (IFRS statements, computed ratios, Beneish M-Score) and financial
modeling results over an HTTP REST API. Client X.509 certificates are
verified by nginx on the host, which forwards the client identity and the
verification status to the service via HTTP headers (X-SSL-Client-Verify,
X-SSL-Client-S-DN, X-SSL-Client-I-DN, X-SSL-Client-Serial,
X-SSL-Client-Fingerprint, X-Client-CN, X-Client-Email).

The API is designed contract-first: `api/openapi.yaml` is the source of
truth. Request/response schemas in `app/schemas.py` must stay in sync with
it.

## Stack

- Python 3.10+, FastAPI, Uvicorn, pydantic v2, pydantic-settings.
- SQLAlchemy 2.0 — ORM models are shared from the root `models.py`
  (PostgreSQL schema `logos`).
- PostgreSQL 18 (Docker, see root `docker-compose.yml`).

## Docker

- `Dockerfile` builds from the repository root (not `mímir/`), because the
  service reuses the root `models.py`.
- The root `docker-compose.yml` starts `mimir` together with `db` (waiting
  for the DB healthcheck) and maps host port `8443`.

## Project structure

```
mímir/
├── api/openapi.yaml        # OpenAPI 3.2 spec (source of truth)
├── app/
│   ├── main.py             # FastAPI application and uvicorn entry point
│   ├── config.py           # settings (env vars, server TLS, DB connection)
│   ├── database.py         # SQLAlchemy engine / session factory
│   ├── schemas.py          # pydantic request/response models
│   └── routers/
│       ├── financials.py   # financial data upload endpoint
│       ├── industries.py   # industries CRUD endpoints
│       └── companies.py    # companies CRUD endpoints
├── tests/                  # pytest tests
├── certs/                  # server + client CA certificates (never commit)
├── Dockerfile              # build from the repository root
├── requirements.txt
└── README.md
```

## Conventions

- Keep `api/openapi.yaml` and `app/schemas.py` in sync.
- Use SQLAlchemy 2.0 `select()` / `session.execute()`; never the legacy
  `Query` API in new code.
- Handlers delegate to the root `crud.py` functions (e.g.
  `add_financial_data`). Reuse the root `models.py`; do not redefine models.
- Follow the root `AGENTS.md` NumPy 2.x / pandas 3.x API rules when
  converting request payloads to `pd.Series` / `pd.DataFrame`.
- Annotate all function parameters and variables with type hints (including
  test fixtures such as `caplog: pytest.LogCaptureFixture`) to minimize
  Pylance warnings.

## Environment variables

- `MIMIR_DB_HOST` — PostgreSQL host (default `localhost`).
- `MIMIR_DB_PORT` — PostgreSQL port (default `5432`).
- `MIMIR_DB_NAME` — PostgreSQL database name (default `finance_db`).
- `MIMIR_DB_USER` — PostgreSQL user (default `logos_user`).
- `MIMIR_DB_PASSWORD` — PostgreSQL password.
- `MIMIR_HOST` — host to bind (default `0.0.0.0`).
- `MIMIR_PORT` — port to bind (default `8443`).
- `MIMIR_SERVER_CERT_FILE` — server TLS certificate (PEM).
- `MIMIR_SERVER_KEY_FILE` — server TLS private key (PEM).

## Testing

Tests live in `tests/` and run against a dedicated PostgreSQL database
(`<POSTGRES_DB>_test`). The database is recreated and migrated with
`alembic upgrade head` for each test session, so the schema matches production.

Install dev dependencies and run pytest from the `mímir/` directory:

```bash
pip install -r requirements-dev.txt
pytest
```

Each test runs inside a transaction that is rolled back afterwards (sessions
join it via savepoints), and `app.dependency_overrides[get_db]` redirects
database access to that transaction.

## Rules

- Do not commit secrets, `.env` files, or certificates (`certs/`).
- After edits, run `python -m compileall app` from the `mímir/` directory to
  validate syntax.
