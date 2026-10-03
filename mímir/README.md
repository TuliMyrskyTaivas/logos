# Mímir

Mímir is the gateway service for the Logos database. It exposes financial
analytics (IFRS statements, computed ratios, Beneish M-Score) and financial
modeling results over an HTTP REST API.

Authentication: mutual TLS (mTLS) using client X.509 certificates.

## API

The API is specified in `api/openapi.yaml` (OpenAPI 3.2, contract-first).

Current endpoints:

| Method | Path          | Description                                          |
| ------ | ------------- | ---------------------------------------------------- |
| POST   | `/financials` | Upload IFRS financial data for a company (upsert).   |

The request body mirrors the `add_financial_data` function in the root
`crud.py`:

- `companyName`, `ticker`, `industryName` — company identity.
- `metrics` — metric code → `{ year: value }`.
- `ratios` — year → `{ ratio name: value }`.

## Development

```bash
python -m venv .venv
.venv\Scripts\Activate.ps1      # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload   # without mTLS, for local development
```

Run with mTLS (see `certs/README.md` and the `MIMIR_*` environment
variables in `AGENTS.md`):

```bash
python -m app.main
```
