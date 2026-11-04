# BFC Cooperative Management System (System A)

The "primary" application that BayanihanDR protects: a small FastAPI + PostgreSQL system for the fictional
**Bicol Farmers Cooperative**, Naga City. **All data is synthetic.**

## What it does

| Area | Endpoints |
|---|---|
| Health | `GET /health` (liveness) · `GET /health/ready` (DB reachable + Alembic schema revision) |
| Members | `GET/POST /api/v1/farmers` · `GET/PATCH/DELETE /api/v1/farmers/{id}` (search `q`, `status`, paging) |
| Inventory | `GET/POST /api/v1/inventory` · `GET/PATCH/DELETE /api/v1/inventory/{id}` (`category`, `low_stock`) |
| Ledger | `GET/POST /api/v1/transactions` · `GET /api/v1/transactions/{id}`. Immutable (no edit/delete). |
| Reports | `GET /api/v1/reports/summary`: member, stock, and ledger totals (also used for DR validation) |

Interactive API docs: http://127.0.0.1:8000/docs

**Business rules:**
- A `sale` (inputs sold to a member) reduces stock and is rejected with 409 if stock is insufficient or the
  member is inactive.
- A `purchase` (the cooperative buys a member's produce) increases stock and only applies to `produce` items.
- A `contribution` adds to the member's share capital, which can't be edited directly.
- Each entry is applied atomically, with row locks.

## Run it

Requires Docker Desktop.

```powershell
cd cooperative-system
copy .env.example .env               # optional: set your own local DB password
docker compose up -d --build --wait  # starts PostgreSQL + API (migrations run automatically)
docker compose exec -T api python -m app.seed   # load the synthetic dataset (1,050 members, 3,000 transactions)
curl http://127.0.0.1:8000/health/ready
```

Ports are bound to `127.0.0.1` only. To stop the app without deleting data: `docker compose stop`.
`docker compose down -v` also **deletes the database volume**, so use it deliberately.

`python -m app.seed --reset` truncates all CMS tables and reseeds. It's destructive and meant for local demos only.

## Test it

```powershell
docker compose --profile test run --rm -T tests
```

Tests run inside the container against a separate `cms_test` database. The suite refuses to run against any
database whose name doesn't end in `_test`. Covered: migrations up/down, health, CRUD and validation for every
resource, ledger rules (stock, inactive members, share capital, immutability), the report summary, and seed
determinism and consistency.

## Layout

```
app/          FastAPI app: models, schemas, services (business rules), routers, seed
migrations/   Alembic migrations (0001_initial_schema)
tests/        pytest suite (real PostgreSQL)
docker/       PostgreSQL init script (creates cms_test)
```

Design decisions: see `docs/DECISIONS.md` (ADR-002 to ADR-005).
