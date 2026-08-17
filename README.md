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
├── alembic/                   # Database migrations (Alembic)
├── alembic.ini                # Alembic configuration
├── docker-compose.yml         # PostgreSQL 18 service
├── requirements.txt           # Python dependencies
├── logos.erm.json             # Entity-relationship model (ERD)
└── README.md
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

3. **Start PostgreSQL:**

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

The script parses all sheets in the Excel file, auto-detects income statement, balance sheet, and cash flow statement sheets by keyword matching (supports both Russian and English), extracts key indicators, computes ratios, and saves everything to the database.

#### Run Scenario Modeling

```bash
# Basic forecast for the next year after the last historical data point
python performance_modeling.py "ACME Corp"

# Forecast a specific year
python performance_modeling.py --year 2027 "ACME Corp"

# Verbose output with debug logging
python performance_modeling.py --verbose "ACME Corp"

# Dry run (no database writes)
python performance_modeling.py --dry-run "ACME Corp"
```

The modeler loads historical data, extrapolates each metric linearly, applies all active scenarios from the database, and outputs a comparison table including revenue, profit, margins, cash flow, breakeven revenue, safety margin, critical revenue drop, and required price increase for each scenario.

## License

See [LICENSE](LICENSE).