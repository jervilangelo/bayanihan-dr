# Changelog

All notable changes to the BayanihanDR blueprint and project are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Blueprint versions track
`docs/MASTER_BLUEPRINT.md`. The v1.0 PDF is preserved unchanged as the original baseline.

## [Unreleased]

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
