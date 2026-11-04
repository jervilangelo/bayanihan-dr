# Changelog

All notable changes to the BayanihanDR blueprint and project are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Blueprint versions track
`docs/MASTER_BLUEPRINT.md`. The v1.0 PDF is preserved unchanged as the original baseline.

## [Unreleased]

### Added (Phase 3)
- `backend/bdr_engine`: the backup engine (System B, part 1).
  - Snapshot-consistent `pg_dump` with manifests (SHA-256, sizes, record counts, schema revision).
  - Verification by restoring into a disposable PostgreSQL and checking the data.
  - Retention with safeguards, an hourly scheduler and a job lock.
  - An event log and a `status.json` for the dashboard.
  - A CLI with a fixed command set: `backup`, `verify`, `list`, `prune`, `status`, `schedule`.
- `cooperative-system/docker-compose.yml`: `backup` profile (`verify-db`, `backup`) and `backup-test` profile.
- Dashboard local operations mode (`npm run dev:ops`).
  - A read-only provider for the engine's `status.json`, served only by the dev server and excluded from the
    Pages build.
  - A new `pending` backup status.
  - Verification checks shown in backup details.
  - Mode-aware Recovery and Overview labels.
- Tests:
  - 35 engine tests, 13 of them integration tests against real PostgreSQL. They cover a repeatable restore and
    detection of corrupted, truncated and tampered backups, missing manifests, failed dumps, unmigrated
    databases and concurrent jobs.
  - 5 new frontend unit tests (31 in total).
- ADR-009 (engine design) and ADR-010 (local schedule and retention).

### Changed (Phase 3)
- Overview's "Next backup" is now the next top of the hour. "Off-site copies" says "Not set up yet" when there are none.
- `.github/workflows/deploy-pages.yml` builds and deploys the dashboard to GitHub Pages.

### Added (Phase 2)
- `frontend/`: the BayanihanDR dashboard, built with React 19, Vite 8, TypeScript, Tailwind 4, Motion,
  Lucide and React Router 8 (hash routing).
  - Five pages: Overview, Backups, Recovery, Activity and Settings.
  - A typed `DashboardProvider` and an in-memory demo provider on a fixed clock, with 72 hours of synthetic
    backups that include a typhoon power cut and one rejected upload.
  - A clearly labelled client-side recovery simulation: preflight checks, recovery-point choice, plan
    preview, explicit approval, live progress, stop, result, and activity logging.
  - Display preferences: PHT or UTC, and reduced motion.
- Tests: 26 Vitest unit tests (dataset, readiness, simulation state machine, provider contract, no network)
  and 48 Playwright tests (24 each on desktop and phone): navigation and deep links, demo labelling, the
  simulation flow, duplicate protection, reduced motion, axe accessibility, and no external requests.
- ADR-006 (hash routing; resolves OD-1), ADR-007 (design system) and ADR-008 (provider and simulation).

### Added (Phase 1)
- Phase 1: Cooperative Management System (`cooperative-system/`): FastAPI + PostgreSQL + Docker Compose,
  Alembic migrations, farmer/inventory/transaction CRUD, reports summary, health checks, synthetic seed data,
  pytest suite.

## [Blueprint 1.0] — 2026-11-04

### Added
- `docs/BayanihanDR_Master_Blueprint_v1.0.pdf`: original baseline (unchanged).
- `docs/MASTER_BLUEPRINT.md`: editable Markdown edition of v1.0. It includes the detailed requirements from the
  master development prompt and adds no architectural changes.
- `docs/CHANGELOG.md` and `docs/DECISIONS.md`.
