# Logos

A toolkit for fundamental analysis of Russian stock market companies. It imports IFRS financial statements from Excel spreadsheets, computes a suite of financial ratios (including the Beneish M-Score for earnings manipulation detection), and runs what-if scenario modeling with breakeven analysis to forecast company performance.

The repository also hosts independent services: **Mímir** (HTTP gateway to the financial data), **Gûldvegt** (precious metals quotes) and **Eign** (private investment portfolio management).

## Features

- **IFRS Import** — Parse income statement, balance sheet, and cash flow statement sheets from Excel files with bilingual (Russian/English) indicator matching.
- **Ratio Calculation** — Automatically compute 13+ financial ratios: ICR, leverage, current ratio, ROFA, FAT, DSRI, GMI, AQI, SGAI, DEPI, LVGI, TATA, SGI, and the Beneish M-Score.
- **Scenario Modeling** — Forecast future financials using linear trend extrapolation, then apply what-if scenarios (multiply, add, set, scale-to-revenue) with breakeven, safety margin, and critical-drop analysis.

## Project Structure

```
logos/
├── models.py                  # SQLAlchemy ORM models (schema `logos`)
├── database.py                # Database connection and session factory
├── crud.py                    # CRUD helpers for importing financial data
├── ratios.py                  # Financial ratio calculations (incl. Beneish M-Score)
├── import_ifrs_from_excel.py  # CLI: import IFRS statements from Excel
├── performance_modeling.py    # CLI: scenario forecasting and breakeven analysis
├── mimir_client.py            # HTTP client for the Mímir service
├── alembic/                   # Database migrations (Alembic)
├── alembic.ini                # Alembic configuration
├── docker-compose.yml         # PostgreSQL 18 + Mímir services
├── requirements.txt           # Python dependencies
├── logos.erm.json             # Entity-relationship model (ERD)
├── README.md
├── mímir/                     # Python (FastAPI) gateway to the database
│   ├── api/openapi.yaml       # OpenAPI 3.2 spec (source of truth)
│   ├── app/                   # FastAPI application (routers, schemas)
│   ├── certs/                 # mTLS certificates (never commit)
│   ├── Dockerfile             # multi-stage Docker build
│   └── requirements.txt
├── gûldvegt/                  # Go HTTP service for precious metals quotes
│   ├── api/openapi.yaml       # OpenAPI 3.2 specification
│   ├── cmd/api/main.go        # echo server entry point
│   ├── internal/api/          # service implementation
│   └── internal/generated/    # oapi-codegen generated code
└── eign/                      # Python (FastAPI) private portfolio service
    ├── spec.md                # requirements draft
    ├── architecture.md        # architecture document
    ├── app/                   # FastAPI app: routers, valuation, performance, jobs
    │   ├── routers/           # API endpoints
    │   ├── jobs/              # APScheduler: price refresh, valuation snapshot
    │   └── marketdata/        # MOEX ISS, CBR and gûldvegt providers
    ├── api/openapi.yaml       # OpenAPI 3.2, exported from FastAPI
    ├── scripts/               # export_openapi.py (spec generation)
    ├── web/                   # Next.js App Router frontend
    ├── alembic/               # own migration chain (schema `eign`)
    ├── tests/                 # pytest suite
    ├── alembic.ini
    ├── requirements.txt
    └── requirements-dev.txt
```

### Database Schema

All tables reside in the `logos` schema and are defined in `models.py`:

| Table | Purpose |
|---|---|
| `industries` | Hierarchical industry classification (self-referencing via `parent_id`) |
| `companies` | Companies with ticker, name, INN, linked to an industry |
| `fiscal_periods` | Reporting periods (annual, Q1, H1, etc.) |
| `metrics` | Financial metric catalog (code, name, category — P&L / BS / CF) |
| `raw_financials` | Actual financial values: company × period × metric |
| `ratios` | Ratio definitions (code, name, formula) |
| `ratio_financials` | Calculated ratio values: company × period × ratio |
| `scenarios` | What-if scenarios for forecasting |
| `scenario_variables` | Individual adjustments (operator + value) within a scenario |
| `forecasts` | Forecasted metric values: company × scenario × year × metric |

See `logos.erm.json` for the full entity-relationship diagram (compatible with ERD tools like [ermaster](https://github.com/nickgak/ER-Master)).

## Gûldvegt

The `gûldvegt/` folder contains a small Go service exposing precious metals
bullion and investment coin quotes over HTTP:

- **Echo v5 server** in `cmd/api/main.go` serves the endpoints from
  `api/openapi.yaml` (OpenAPI 3.2): `GET /quotes/bullions` and
  `GET /quotes/coins`.
- **Generated code** in `internal/generated/openapi/` is produced with
  [oapi-codegen](https://github.com/oapi-codegen/oapi-codegen) from the spec
  (`codegen.yaml` for models, `codegen-server.yaml` for the echo server).
- **Service implementation** in `internal/api/` returns sample quote data.

Run it with:

```bash
cd gûldvegt
go run ./cmd/api
```

## Mímir

Mímir is a Python (FastAPI) gateway to the Logos PostgreSQL database. It
exposes financial analytics (IFRS statements, ratios, Beneish M-Score) and
modeling results over an HTTP REST API. The API is specified contract-first in
`mímir/api/openapi.yaml` (OpenAPI 3.2), and authentication is performed with
mutual TLS (mTLS) using client X.509 certificates.

Endpoints:

| Method | Path                        | Description                               |
| ------ | --------------------------- | ----------------------------------------- |
| POST   | `/financials`               | Upload IFRS financial data (upsert)       |
| GET    | `/companies`                | List companies (`?name=`, `?industryId=`) |
| POST   | `/companies`                | Create a company                          |
| PATCH  | `/companies/{id}`           | Update a company                          |
| DELETE | `/companies/{id}`           | Delete a company and its financial data   |
| GET    | `/companies/{id}/financials`| Get historical metrics and ratios         |
| PUT    | `/companies/{id}/forecasts` | Save forecast results (upsert)            |
| GET    | `/industries`               | List industries                           |
| POST   | `/industries`               | Create an industry                        |
| PATCH  | `/industries/{id}`          | Update an industry                        |
| DELETE | `/industries/{id}`          | Delete an industry                        |
| GET    | `/scenarios`                | List scenarios (`?isActive=`)             |
| GET    | `/scenarios/{id}/variables` | List scenario variables                   |

The CLI tools `import_ifrs_from_excel.py` and `performance_modeling.py` talk to
Mímir over HTTP through the shared `mimir_client.py` instead of writing to the
database directly.

Run it with:

```bash
cd mímir
pip install -r requirements.txt
python -m app.main
```

The service listens on `0.0.0.0:8443` by default (`MIMIR_HOST`/`MIMIR_PORT`).
When `MIMIR_SERVER_CERT_FILE`, `MIMIR_SERVER_KEY_FILE` and
`MIMIR_CLIENT_CA_FILE` are set, it serves HTTPS with mutual TLS. See
`mímir/AGENTS.md` for the full list of `MIMIR_*` environment variables.

## Eign

Eign (Old Norse *eign* — "property, holding, asset") manages a private
investment portfolio: current valuation, asset allocation, performance and risk
metrics, trade history, trade planning, income plan/fact and portfolio goals.
Requirements are in [`eign/spec.md`](eign/spec.md), the design is in
[`eign/architecture.md`](eign/architecture.md).

### How it is built

- **FastAPI** service (Python 3.10+): SQLAlchemy 2.0, pydantic v2, Alembic,
  APScheduler.
- **Own schema `eign`** in the shared Logos database with a **separate
  migration chain** (version table `alembic_version_eign`), so it never
  interferes with the `logos` schema migrations.
- **Two database roles with separated privileges**:
  - `eign_frontend` — API requests: positions, trades, plans, income, goals,
    manual quotes; read-only access to valuation snapshots;
  - `eign_backend` — background jobs: market prices and valuation snapshots;
    no write access to positions or trades.
- **Authentication via mTLS**: nginx verifies the client certificate and
  forwards `X-SSL-Client-Verify` / `X-Client-CN`; the first user automatically
  becomes an administrator who creates the others.

### Market data

Prices are cached in the `prices` table and refreshed by a background job:

| Source | Used for |
|---|---|
| MOEX ISS | shares, bonds (price is converted from percent of face value), funds by ticker or ISIN |
| CBR RF | currency rates (stored as `currency` rows in `prices`) |
| gûldvegt | precious metals, median price per gram of bullion quotes |
| manual | entered via API; takes precedence over a fetched quote of the same day |

A position is valued by the newest quote of its instrument; if none exists the
manually maintained `currentPrice` is used, otherwise the position is reported
as unpriced instead of silently valued at zero.

### Main endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/auth/me` | current user (created as admin on the very first request) |
| GET/POST | `/users`, PATCH/DELETE `/users/{id}` | user management (admin only) |
| GET | `/asset-classes` | asset class dictionary |
| GET/POST | `/assets`, GET/PATCH/DELETE `/assets/{id}` | positions |
| GET/POST | `/trades`, PATCH/DELETE `/trades/{id}` | trades; the position is recalculated (weighted average cost) |
| GET/POST | `/trade-plan`, PATCH/DELETE `/trade-plan/{id}` | planned trades with cumulative execution against the month's trades |
| GET/POST | `/income`, PATCH/DELETE `/income/{id}` | income plan/fact per position and month |
| GET | `/income/summary` | plan/fact per month of a year in the base currency |
| POST | `/prices` | manual quote for an instrument |
| GET | `/portfolio/summary` | current value, allocation by class, unpriced positions, income YTD |
| GET | `/portfolio/performance` | TWR, XIRR, annualised volatility, max drawdown, Sharpe/Sortino |
| GET/PUT | `/goals` | target value (fiat or metal), target allocation, target return |
| GET | `/goals/progress` | progress against value, allocation and return targets |
| GET | `/valuations` | stored monthly valuation snapshots |
| GET | `/valuations/latest` | latest snapshot |
| GET | `/health` | liveness probe |

### Database Schema

All Eign tables live in the `eign` schema: `users`, `asset_classes`, `assets`,
`trades`, `trade_plan`, `income_plan_fact`, `goals`, `goal_allocations`,
`valuations`, `valuation_items`, `prices`.

### Background jobs

APScheduler runs inside the API process (`EIGN_SCHEDULER_ENABLED=false`
disables it):

- `EIGN_PRICES_CRON` (default `30 18 * * 1-5`) — refresh quotes for every
  instrument used by positions and CBR rates for the currencies in use;
- `EIGN_VALUATION_CRON` (default `0 3 1 * *`) — store a valuation snapshot per
  active user; repeated runs for the same date update the snapshot instead of
  duplicating it.

### Frontend

The Next.js (App Router) application in [`eign/web`](eign/web) renders the
portfolio screens: `/portfolio/summary` (valuation, allocation, performance and
risk metrics), `/assets` (positions with create/edit/delete), `/trades` (trade
history, registration and corrections with position recalculation), `/plan`
(monthly trade plan with progress from the month's trades), `/income` (income
plan/fact per year with execution to date) and `/goals` (target value in a
currency or grams of metal, target return and target allocation). Administrators
additionally get `/users` to create accounts and manage roles. The root `/`
redirects to the summary.

- Server components call the API at `EIGN_API_URL` and forward the identity
  headers set by nginx (`X-Client-CN` / `X-SSL-Client-Verify`). Mutations and
  other browser calls go through the same-origin `/api/*` proxy, which nginx
  serves directly in production and `next dev` serves through a route handler.
  Outside nginx the login falls back to `EIGN_DEV_LOGIN` and the header shows a
  `dev identity` badge; with neither the app renders "Client certificate
  required" instead of portfolio data.
- Types are generated from the committed OpenAPI document
  (`eign/api/openapi.yaml`, produced by `eign/scripts/export_openapi.py`) into
  `eign/web/lib/api-types.ts`; regenerate them with `npm run api:types`.

### Run locally

Prerequisites: PostgreSQL 18 on `localhost:5432` (see
[Getting Started](#getting-started)), Python 3.10+ with the service
requirements, and Node.js 20.9+ for the frontend. Commands are PowerShell; on
bash/macOS replace `$env:NAME = "value"` with `export NAME=value`.

#### Backend

```powershell
cd eign
..\.venv\Scripts\Activate.ps1        # or activate your own virtualenv
pip install -r requirements.txt

# One-off: migrations run as the database superuser because they create the
# `eign` schema and the eign_frontend/eign_backend roles. Credentials come from
# the repository `.env` (POSTGRES_*, EIGN_FRONTEND_PASSWORD,
# EIGN_BACKEND_PASSWORD); variables already present in the environment win, so
# export them only to override the file.
alembic upgrade head

# The API itself connects with the technical roles created above; their
# passwords are the EIGN_FRONTEND_PASSWORD / EIGN_BACKEND_PASSWORD values.
$env:EIGN_DB_USER = "eign_frontend"
$env:EIGN_DB_PASSWORD = "<EIGN_FRONTEND_PASSWORD>"
$env:EIGN_DB_BACKEND_USER = "eign_backend"
$env:EIGN_DB_BACKEND_PASSWORD = "<EIGN_BACKEND_PASSWORD>"
python -m app.main
```

`alembic/env.py` loads the repository `.env` with `override=False`: real
environment variables win over the file, and a partly exported `POSTGRES_*`
set no longer gets mixed with the defaults (an unset `POSTGRES_USER` used to
fall back to `postgres`, which fails authentication against a database owned by
another user).

The migration creates `eign_frontend`/`eign_backend` only when they are absent;
if the roles already exist their current passwords are kept. In that case use
those passwords in `EIGN_DB_PASSWORD`/`EIGN_DB_BACKEND_PASSWORD`, or rotate them
with `ALTER ROLE`.

The API listens on `0.0.0.0:8080` (`EIGN_HOST`/`EIGN_PORT`); the liveness probe
is `GET /health`. TLS and client certificate verification are expected to be
terminated by nginx in front of it; the container and nginx setup is described
in `eign/architecture.md` (§12).

#### Logs

Both loggers write to **stderr**: uvicorn (`INFO: 127.0.0.1:... "GET /path"
200 OK`, tracebacks of unhandled errors) and `eign.access` (the identity
headers of every request). A background process that discards its output
therefore shows nothing, so keep the log:

```powershell
# one terminal, log on screen and in the file
python -m app.main *>&1 | Tee-Object -FilePath eign-backend.log

# or fully detached, then follow the file
Start-Process -FilePath "..\.venv\Scripts\python.exe" -ArgumentList "-m","app.main" `
  -RedirectStandardOutput eign-backend.log -RedirectStandardError eign-backend.err
Get-Content eign-backend.log, eign-backend.err -Wait -Tail 50
```

`EIGN_LOG_LEVEL` sets the verbosity of both (default `INFO`, use `debug` for
more detail). To call the API without nginx, pass the identity headers
yourself:

```powershell
$h = @{ "X-Client-CN" = "admin"; "X-SSL-Client-Verify" = "SUCCESS" }
Invoke-RestMethod http://localhost:8080/auth/me -Headers $h      # 200, 401 or 403
Invoke-RestMethod http://localhost:8080/portfolio/summary -Headers $h
```

`401` means the headers are missing or `X-SSL-Client-Verify` is not `SUCCESS`;
`403` means the login is not registered (the users table is non-empty and the
login was never created) or the user is deactivated.

Other settings: `EIGN_DB_HOST`/`EIGN_DB_PORT`/`EIGN_DB_NAME`, `EIGN_TZ`,
`EIGN_GULDVEGT_URL`, `EIGN_MOEX_URL`, `EIGN_CBR_URL`,
`EIGN_MARKETDATA_TIMEOUT`, `EIGN_RISK_FREE_RATE`.

#### Frontend

Run the backend first: the pages are rendered on the server and call the API
directly. In a second terminal:

```powershell
cd eign/web
npm install
npm run api:types
$env:EIGN_API_URL = "http://localhost:8080"   # default
$env:EIGN_DEV_LOGIN = "admin"                 # stand-in for the certificate CN
npm run dev                                  # http://localhost:3000
```

`EIGN_DEV_LOGIN` is only for local work: it replaces the missing mTLS headers,
so the page shows a `dev identity` badge. The login must be one the API knows
about — the very first request creates it as the administrator. Omit the
variable to see the "Client certificate required" screen instead.

Next dev prints the reason of every 500 (stack trace, failing file, line) in the
terminal that runs `npm run dev`, so keep that output as well:

```powershell
npm run dev *>&1 | Tee-Object -FilePath eign-web.log
```

If the backend log shows no `/auth/me` request at all, the frontend never
reached the API: check `EIGN_API_URL` and that the backend is still listening
(`Invoke-RestMethod http://localhost:8080/health`).

`npm run typecheck` and `npm run build` are the production checks. See
[`eign/web/README.md`](eign/web/README.md) for the full script list and the
`web/` layout.

### Tests

```bash
cd eign
pip install -r requirements-dev.txt
pytest
```

Each run recreates a dedicated `<POSTGRES_DB>_eign_test` database, applies the
Eign migrations to it, and rolls every test back through a savepoint.

## Getting Started

### Prerequisites

- Python 3.10+
- Docker and Docker Compose
- PostgreSQL client (optional, for direct DB access)

### Setup

1. **Clone the repository:**

   ```bash
   git clone https://github.com/TuliMyrskyTaivas/logos.git
   cd logos
   ```

2. **Create a `.env` file** with PostgreSQL credentials:

   ```env
   POSTGRES_DB=financial_db
   POSTGRES_USER=postgres
   POSTGRES_PASSWORD=postgres
   ```

3. **Start PostgreSQL and Mímir:**

   ```bash
   docker compose up -d
   ```

4. **Install Python dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

5. **Run database migrations:**

   ```bash
   alembic upgrade head
   ```

### Usage

#### Import IFRS Data from Excel

```bash
python import_ifrs_from_excel.py reports.xlsx \
  --company "ACME Corp" \
  --ticker ACME \
  --industry "Oil & Gas" \
  --verbose
```

The script parses all sheets in the Excel file, auto-detects income statement, balance sheet, and cash flow statement sheets by keyword matching (supports both Russian and English), extracts key indicators, computes ratios, and uploads the results to the Mímir service. Point it at the service with `--mimir-url` (or the `MIMIR_URL` environment variable).

#### Run Scenario Modeling

```bash
# Basic forecast for the next year after the last historical data point
python performance_modeling.py "ACME Corp"

# Forecast a specific year
python performance_modeling.py --year 2027 "ACME Corp"

# Verbose output with debug logging
python performance_modeling.py --verbose "ACME Corp"

# Dry run (does not save results)
python performance_modeling.py --dry-run "ACME Corp"
```

The modeler loads historical data, extrapolates each metric linearly, applies all active scenarios, and outputs a comparison table including revenue, profit, margins, cash flow, breakeven revenue, safety margin, critical revenue drop, and required price increase for each scenario. Results are saved through the Mímir service (`--mimir-url` / `MIMIR_URL`), unless `--dry-run` is passed.

## License

See [LICENSE](LICENSE).