# BayanihanDR

**Terraform-powered disaster recovery for Philippine small businesses.** It's a portfolio proof of concept. When a
typhoon takes the fictional Bicol Farmers Cooperative's on-premises server offline, BayanihanDR restores its
Cooperative Management System in AWS (`ap-southeast-1`) from verified, encrypted off-site backups, and measures
how long recovery actually took.

> Status: **Phases 1–2 of 10 complete (local CMS, dashboard with a simulated recovery).** No AWS resources exist yet. Recovery metrics will be published only
> after a real, measured drill. Nothing here is a claimed result yet.

| System | Folder | Status |
|---|---|---|
| A. Cooperative Management System (FastAPI + PostgreSQL + Docker Compose) | [`cooperative-system/`](cooperative-system/) | ✅ Phase 1 |
| B. Recovery engine (backups, Terraform orchestration, restore, metrics) | `backend/`, `scripts/`, `terraform/` | Planned (Phases 3–7) |
| C. Dashboard (React + Vite; local ops mode + public GitHub Pages demo) | [`frontend/`](frontend/) | ✅ Phase 2 (demo mode; ops mode in Phase 6) |

Recovery targets (design goals, **not yet measured**): RTO 30 minutes, RPO 1 hour.

## Documentation

- [Master blueprint](docs/MASTER_BLUEPRINT.md): scope, architecture, phases, security, cost controls
- [Decision log](docs/DECISIONS.md) · [Changelog](docs/CHANGELOG.md)
- Original baseline: [`docs/BayanihanDR_Master_Blueprint_v1.0.pdf`](docs/BayanihanDR_Master_Blueprint_v1.0.pdf)

## Quick start (CMS)

See [`cooperative-system/README.md`](cooperative-system/README.md).

All data in this project is synthetic. No real farmer, employee, or financial records are used.
