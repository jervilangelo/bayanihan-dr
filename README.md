# BayanihanDR

**Terraform-powered disaster recovery for Philippine small businesses.** It's a portfolio proof of concept. When a
typhoon takes the fictional Bicol Farmers Cooperative's on-premises server offline, BayanihanDR restores its
Cooperative Management System in AWS (`ap-southeast-1`) from verified, encrypted off-site backups, and measures
how long recovery actually took.

> Status: **Phases 1–5 of 10 complete.** The AWS standby environment is deployed (encrypted backup bucket, IAM, logs, budget alert; no EC2 running), and verified backups are stored off-site and read back. Recovery metrics will be published only after a real,
> measured drill. Nothing here is a claimed result yet.

| System | Folder | Status |
|---|---|---|
| A. Cooperative Management System (FastAPI + PostgreSQL + Docker Compose) | [`cooperative-system/`](cooperative-system/) | ✅ Phase 1 |
| B. Recovery engine (backups, Terraform orchestration, restore, metrics) | [`backend/`](backend/), [`terraform/`](terraform/) | ✅ Phase 3 (local backups + restore verification); ✅ Phase 4 (Terraform, plan-only); Phases 5–7 planned |
| C. Dashboard (React + Vite; local ops mode + public GitHub Pages demo) | [`frontend/`](frontend/) | ✅ Phase 2 (public demo); read-only local ops mode in Phase 3 |

Recovery targets (design goals, **not yet measured**): RTO 30 minutes, RPO 1 hour.

## Documentation

- [Master blueprint](docs/MASTER_BLUEPRINT.md): scope, architecture, phases, security, cost controls
- [Decision log](docs/DECISIONS.md) · [Changelog](docs/CHANGELOG.md)
- Original baseline: [`docs/BayanihanDR_Master_Blueprint_v1.0.pdf`](docs/BayanihanDR_Master_Blueprint_v1.0.pdf)

## Quick start

- CMS: [`cooperative-system/README.md`](cooperative-system/README.md)
- Backups: [`backend/README.md`](backend/README.md). Run `docker compose --profile backup up -d --build` in `cooperative-system/`.
- Dashboard: in `frontend/`, run `npm run dev` for the demo, or `npm run dev:ops` to see real local backups.

All data in this project is synthetic. No real farmer, employee, or financial records are used.
