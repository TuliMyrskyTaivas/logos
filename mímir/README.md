# Mímir

Mímir is the gateway service for the Logos database. It exposes financial
analytics (IFRS statements, computed ratios, Beneish M-Score) and financial
modeling results over an HTTP REST API.

Authentication: client X.509 certificates are verified by nginx on the host.
The service receives the verified identity through HTTP headers forwarded by
nginx: X-SSL-Client-Verify, X-SSL-Client-S-DN, X-SSL-Client-I-DN,
X-SSL-Client-Serial, X-SSL-Client-Fingerprint, X-Client-CN, X-Client-Email.

## API

The API is specified in `api/openapi.yaml` (OpenAPI 3.2, contract-first).

Current endpoints:

| Method | Path               | Description                                          |
| ------ | ------------------ | ---------------------------------------------------- |
| POST   | `/financials`      | Upload IFRS financial data for a company (upsert).   |
| GET    | `/industries`      | List industries (optional `?id=` and `?name=`).      |
| POST   | `/industries`      | Create an industry.                                  |
| PATCH  | `/industries/{id}` | Update an industry.                                  |
| DELETE | `/industries/{id}` | Delete an industry.                                  |
| GET    | `/companies`       | List companies (optional `?industryId=`, `?industryParentId=`, `?name=`). |
| POST   | `/companies`       | Create a company.                                    |
| PATCH  | `/companies/{id}`  | Update a company.                                    |
| DELETE | `/companies/{id}`  | Delete a company.                                    |

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
uvicorn app.main:app --reload   # for local development
```

Run the server directly (server TLS is enabled when
`MIMIR_SERVER_CERT_FILE` and `MIMIR_SERVER_KEY_FILE` are set):

```bash
python -m app.main
```
