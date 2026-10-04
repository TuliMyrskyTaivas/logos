# Logos

A toolkit for fundamental analysis of Russian stock market companies. It imports IFRS financial statements from Excel spreadsheets, computes a suite of financial ratios (including the Beneish M-Score for earnings manipulation detection), and runs what-if scenario modeling with breakeven analysis to forecast company performance.

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
└── gûldvegt/                  # Go HTTP service for precious metals quotes
    ├── api/openapi.yaml       # OpenAPI 3.2 specification
    ├── cmd/api/main.go        # echo server entry point
    ├── internal/api/          # service implementation
    └── internal/generated/    # oapi-codegen generated code
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