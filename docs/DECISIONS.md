# Architecture Decision Log

Each decision records its context, the choice, and its consequences. Status values: **Proposed**, **Accepted**,
**Superseded**. Material architecture changes need the project owner's approval before they are marked Accepted.

---

## ADR-001 — Markdown blueprint is the living source of truth

- **Status:** Accepted (required by the blueprint's own document control)
- **Date:** 2026-11-04
- **Context:** The v1.0 PDF is hard to diff and edit.
- **Decision:** `docs/MASTER_BLUEPRINT.md` is the editable source of truth. The PDF stays as the immutable v1.0
  baseline. New versioned PDFs are proposed at major milestones.
- **Consequences:** Every material change updates the Markdown blueprint, `CHANGELOG.md`, and this log.

## ADR-002 — CMS stack: SQLAlchemy 2.0 + Alembic + psycopg 3

- **Status:** Accepted (implementation detail inside the approved FastAPI + PostgreSQL stack)
- **Date:** 2026-11-04
- **Context:** Phase 1 requires database migrations and CRUD against PostgreSQL.
- **Decision:** Use SQLAlchemy 2.0 ORM models, Alembic for versioned migrations, and the psycopg 3 driver. Use
  synchronous endpoints for simplicity.
- **Consequences:** Widely known, interview-friendly tools. The Alembic revision is reported by the readiness health
  check so a restored database's schema version can be verified during recovery.

## ADR-003 — CMS runs in containers on Python 3.12; tests run against real PostgreSQL

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** The host has Python 3.14, which some binary wheels may lag behind. Recovery happens on a Linux EC2
  host, so the container image is what actually gets recovered.
- **Decision:** The API image uses `python:3.12-slim`, and PostgreSQL uses `postgres:16-alpine`. Tests run inside
  the API container against a separate `cms_test` database on the same PostgreSQL server, not SQLite, so
  Postgres-specific behavior (constraints, numerics, `SELECT … FOR UPDATE`) is exercised.
- **Consequences:** Running tests requires Docker. Local and recovery environments use identical images.

## ADR-004 — Transactions are immutable ledger entries

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** Sales, produce purchases, and share-capital contributions affect stock and balances. Editing or
  deleting them would silently corrupt totals, which also makes post-recovery validation unreliable.
- **Decision:** Transactions support create, list, and get only. Each create atomically updates inventory or the
  member's share capital in one database transaction, with row locks. Corrections are new entries (a future
  feature). Sales that exceed stock are rejected with HTTP 409.
- **Consequences:** Report totals are derived from an append-only ledger, which gives the DR drill deterministic
  record checks.

## ADR-005 — Deterministic synthetic seed data

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** Data must be synthetic, and recovery validation needs known records.
- **Decision:** A seeded pseudo-random generator (`random.Random(2026)`) produces 1,050 members, a fixed inventory
  catalogue, and a fixed number of transactions. Names come from hard-coded lists of common Filipino given names and
  surnames, combined at random, and are not real people. Phone numbers use the reserved-looking `0900-000-xxxx`
  pattern. Seeding refuses to run on a non-empty database unless `--reset` is given.
- **Consequences:** Every fresh seed produces identical counts and totals, which Phase 7 can assert against.

## ADR-006 — Hash routing for the dashboard (resolves OD-1)

- **Status:** Accepted (implemented in Phase 2; the project owner can still override it)
- **Date:** 2026-11-04
- **Context:** GitHub Pages has no server-side rewrites. A browser router needs a `404.html` copy of the
  app, and with it direct links return HTTP 404 before the app recovers.
- **Decision:** Use React Router's `createHashRouter` (`…/bayanihan-dr/#/backups`) with Vite `base: '/bayanihan-dr/'`.
- **Consequences:** Direct links and refreshes always work with no server configuration. Playwright verifies
  this for all five pages. URLs carry a `#`, which is acceptable for a dashboard.

## ADR-007 — Dashboard design system: TasteSkill "accent ladder" on the blueprint palette

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** The blueprint fixes the palette. TasteSkill deals an app style; UI/UX Pro Max's
  `--design-system` suggested a navy palette with Fira Code headings.
- **Decision:**
  - Use TasteSkill's `accent-ladder` style (seed 1642492960) with `--keep palette`. The full sage `#397D6A`
    goes on small marks only: data, the one filled button, and the active nav icon. Pale `#DCEDE7` covers areas.
  - Type is DM Sans, self-hosted through `@fontsource`, so there are no external requests.
  - UI/UX Pro Max's palette and monospace headings were **not** adopted. They conflict with the blueprint
    palette and with TasteSkill's ban on monospace display type. Its accessibility and interaction
    checklist was applied.
  - TasteSkill says app screens should have no entrance motion, but the blueprint requires subtle staggered
    entrances and page transitions. **The blueprint wins.** Motion is kept to opacity plus 6px over
    150–250 ms. It is removed under `prefers-reduced-motion` and under the in-app "Reduce motion" setting.
- **Consequences:** The design is distinctive without breaking the blueprint. Inspector results:
  0 FAIL / 0 WARN on all five pages at 1440, 768 and 390px.

## ADR-008 — Typed provider interface; demo provider with a fixed clock and client-side simulation

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** The blueprint requires one dashboard with two modes: a public demo and local operations.
  The public demo must never trigger AWS or Terraform.
- **Decision:**
  - Pages depend only on the `DashboardProvider` interface (`frontend/src/data/types.ts`).
  - The demo provider is in-memory, holds no credentials, and makes no network calls. Unit tests stub
    `fetch` to throw, and Playwright fails on any request that leaves the site.
  - Demo data runs on a fixed clock (13:52 PHT, 4 Nov 2026), so every visitor and every test sees the same story.
  - The recovery simulation is a pure state machine (`jobStateAt`) driven by the real clock and a playback speed.
  - Step durations are whole-minute placeholders, labelled as simulated everywhere.
  - Duplicate-job protection exists in the demo too, because the same contract will apply to the real
    backend (Phase 6).
- **Consequences:** Phase 6 adds an operational provider behind the same interface without rewriting pages.

---

## Open decisions (from blueprint v1.0)

| # | Question | Target phase |
|---|---|---|
| OD-1 | ~~HashRouter vs static route fallback for GitHub Pages~~ Resolved by ADR-006 | Phase 2 ✔ |
| OD-2 | Terraform remote-state backend + locking; bootstrap and residual cost | Phase 4 |
| OD-3 | Recovery access: SSM Session Manager (preferred) vs restricted SSH | Phase 4 |
| OD-4 | Backup schedule/retention, encryption key management (SSE-S3 vs SSE-KMS), restore-test cadence | Phase 3 |
| OD-5 | Local authentication method; how alternate-workstation recovery is started | Phase 6 |
| OD-6 | Verify current `ap-southeast-1` pricing and final test budget | Phase 5 |
