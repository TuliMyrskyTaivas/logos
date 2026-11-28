# eign-web

Next.js (App Router) frontend of the Eign portfolio service.

| Route | Purpose |
| --- | --- |
| `/portfolio/summary` | valuation, allocation, performance and risk metrics, positions |
| `/assets` | positions: table with sorting/search/class filter, create, edit, delete |
| `/trades` | trade history with filters, register, correct and delete trades |
| `/income` | income plan/fact per year: totals, execution to date, monthly chart, rows CRUD |
| `/plan` | monthly trade plan: targets per position or class (money or units), progress from the month's trades, planned/executed/cancelled |
| `/goals` | target value (currency or metal), target return vs annualised TWR, target vs actual allocation |
| `/users` | **admin only**: accounts with role and status, create, promote/demote, deactivate and activate |

`/` redirects to `/portfolio/summary`.

## Requirements

- Node.js 20.9+ and npm.
- A running Eign API (see `../README.md`), reachable at `EIGN_API_URL`.

## Configuration

Copy `.env.example` to `.env.local`:

| Variable | Purpose |
| --- | --- |
| `EIGN_API_URL` | Base URL of the Eign API as seen from the Next.js server. Default: `http://localhost:8080`. |
| `EIGN_DEV_LOGIN` | **Development only.** Login to act as when nginx does not provide the mTLS headers. Never set it in a deployed environment. |

Eign has no login form: the identity is the Common Name of the client
certificate, verified by nginx. In development `EIGN_DEV_LOGIN` replaces it and
the header shows a `dev identity` badge.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Development server on `http://localhost:3000`. |
| `npm run build` | Production build (`output: "standalone"`). |
| `npm start` | Serve the production build. |
| `npm run typecheck` | `tsc --noEmit`. |
| `npm run api:types` | Regenerate `lib/api-types.ts` from `../api/openapi.yaml`. |

## Contract

API types are generated from the committed OpenAPI document:

```powershell
python ..\scripts\export_openapi.py   # refresh ../api/openapi.yaml from FastAPI
npm run api:types                     # regenerate lib/api-types.ts
```

`lib/api-types.ts` is committed so a clean checkout type-checks without an
extra step; regenerate it whenever the backend schemas change.

## Data flow

- Server components call the API directly at `EIGN_API_URL` (`lib/api.ts`) and
  forward the identity headers.
- Browser code goes through the same-origin proxy `app/api/[...path]/route.ts`
  (`lib/client-api.ts`). In production nginx routes `/api/*` to the backend
  itself, so the handler only matters for `next dev`; it forwards to
  `EIGN_API_URL` only.
- After a mutation the views call `router.refresh()`; responses are never cached.
- `lib/types.ts` holds the generated schema types and `ApiError` without server
  imports, so client components never pull `next/headers` into the browser
  bundle.

Tables use TanStack Table v8 (`@tanstack/react-table@^8`): v9 reworked the API
(`tableFeatures`/`useTable`), so the major version is pinned until the tables
are migrated deliberately.

> **Do not copy `data` when passing it to `useReactTable`.** TanStack memoises
> the row model on the identity of the array and re-triggers its page-index
> auto-reset when that identity changes. `data: [...rows]` therefore produces an
> endless render loop: the first interaction (a click, typing in the search
> field) freezes the tab, with tens of thousands of DOM mutations per second.
> Pass the memoised array itself and keep `autoResetPageIndex: false` while
> pagination is not used.

## Layout

```
app/
├── layout.tsx              # session, shell, identity screens
├── page.tsx                # redirect to /portfolio/summary
├── globals.css             # Tailwind 4 theme (light/dark)
├── api/[...path]/route.ts  # same-origin proxy to the Eign API
├── portfolio/summary/      # page, loading skeleton, error boundary
├── assets/                 # positions page (+ loading, error)
├── trades/                 # trades page (+ loading, error)
├── plan/                   # trade plan page (+ loading, error); month via ?month=
├── income/                 # income page (+ loading, error); year via ?year=
├── goals/                  # goals page (+ loading, error)
└── users/                  # users page (+ loading, error); admin only
components/
├── assets/                 # table, form and view of positions
├── trades/                 # table, form and view of trades
├── plan/                   # plan table with progress bars, form and view
├── income/                 # table, form, view and plan-vs-fact chart
├── goals/                  # goal form and allocation comparison
├── users/                  # accounts table and creation form
├── ui/                     # button, field, modal, card, table, alert
├── nav.tsx                 # section navigation
└── ...                     # KPI cards, charts, positions table
lib/
├── types.ts                # schema types + ApiError (client-safe)
├── api.ts                  # server-side GETs
├── client-api.ts           # browser calls through /api/*
├── api-types.ts            # generated from openapi.yaml
├── identity.ts             # nginx headers and the development fallback
├── session.ts              # identity + GET /auth/me
├── format.ts               # Intl money/percent/date formatting
├── metrics.ts              # metric tone and unpriced reasons
└── utils.ts                # cn()
```
