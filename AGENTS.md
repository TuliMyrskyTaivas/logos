# AGENTS.md

Guidelines for AI coding agents working in this repository.

## Project Overview

Logos is a Python toolkit for fundamental analysis of Russian stock market
companies. It imports IFRS financial statements from Excel spreadsheets,
computes financial ratios (including the Beneish M-Score), and runs what-if
scenario modeling with breakeven analysis.

## Project Structure

```
logos/
├── models.py                  # SQLAlchemy 2.0 ORM models (schema `logos`)
├── database.py                # Database connection and session factory
├── crud.py                    # CRUD helpers for importing financial data
├── ratios.py                  # Financial ratio calculations (incl. Beneish M-Score)
├── import_ifrs_from_excel.py  # CLI: import IFRS statements from Excel
├── performance_modeling.py    # CLI: scenario forecasting and breakeven analysis
├── alembic/                   # Database migrations (Alembic)
├── alembic.ini                # Alembic configuration
├── docker-compose.yml         # PostgreSQL 18 service
├── requirements.txt           # Python dependencies
├── logos.erm.json             # Entity-relationship model (ERD)
├── README.md
└── gûldvegt/                  # Go HTTP service for precious metals quotes
    ├── api/openapi.yaml       # OpenAPI 3.2 specification
    ├── cmd/api/main.go        # echo server entry point
    ├── internal/api/          # service implementation
    └── internal/generated/    # oapi-codegen generated code
```

- **Stack:** Python 3.10+, PostgreSQL 18 (Docker), SQLAlchemy, Alembic,
  pandas, NumPy, SciPy, openpyxl.
- **ORM layer:** all tables live in the `logos` schema and are defined in
  `models.py` using `DeclarativeBase`.
- **Migrations:** managed with Alembic (`alembic/versions/`).
- **CLI entry points:** `import_ifrs_from_excel.py` and
  `performance_modeling.py`.

### Gûldvegt (Go service)

The `gûldvegt/` folder is a separate Go module that serves precious metals
bullion and investment coin quotes over HTTP:

- Echo v5 server (`cmd/api/main.go`) exposing `GET /quotes/bullions` and
  `GET /quotes/coins`, as defined in `api/openapi.yaml` (OpenAPI 3.2).
- Generated code in `internal/generated/openapi/` via
  [oapi-codegen](https://github.com/oapi-codegen/oapi-codegen); regenerate
  with `codegen.yaml` (models) and `codegen-server.yaml` (echo server).
  Do not edit generated files by hand.
- Service implementation in `internal/api/`.

## General Rules

- Read `README.md` and relevant source files before making changes.
- Keep changes minimal and focused; do not refactor unrelated code.
- Preserve existing code style, naming conventions, and type hints.
- Do not modify generated files (e.g. `logos.erm.json`,
  `logos.erm.layout.json`) by hand.
- Do not commit secrets, credentials, or `.env` files.
- After edits, run the relevant checks (e.g. `python -m compileall` or the
  existing test/CLI commands) to validate changes.

## Strict API Rules

Use **only modern versions** of the following APIs. Never fall back to
legacy/deprecated styles.

### SQLAlchemy (2.0+)

- Use the 2.0 declarative style: `DeclarativeBase`, `Mapped[...]`,
  `mapped_column()`, and typed relationships.
- Query with the 2.0 `select()` statement and `Session.execute(...)`
  (e.g. `session.execute(select(Model).where(...))`).
- Do **not** use legacy `Query` API (`session.query(...)`) in new code,
  `Column(...)`/`declarative_base()`, or `relationship(backref=...)`.
- Use `sessionmaker` for session factories.

### NumPy (2.x)

- Use the current NumPy 2.x API and dtype/`np.` conventions.
- Do not use removed aliases (`np.float_`, `np.int_`, `np.bool8`, etc.) or
  deprecated scalar constructors; use `float`, `int`, `bool` or explicit
  NumPy dtypes instead.
- Avoid deprecated functions and follow current `numpy` documentation.

### pandas (3.x)

- Use the current pandas 3.x API.
- Prefer copy-on-write-safe patterns: avoid chained assignment
  (`df[...][...] = ...`); use `.loc`/`.iloc` or `.assign()`.
- Do not use deprecated methods/arguments (e.g. old `inplace=`-dependent
  idioms, `iteritems()`, `append()`, `ix`); follow current `pandas`
  documentation.
