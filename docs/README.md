# BayanihanDR documentation

Start here when you come back to the project.

## Read first

| Document | When you need it |
|---|---|
| [../README.md](../README.md) | What the project is, its status, the results, quick start |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the three systems fit together: diagrams, data flows, trust boundaries, repository map |
| [RUNBOOK.md](RUNBOOK.md) | **Doing things:** daily checks, backups and off-site copies, drills, a real disaster recovery, teardown, troubleshooting |
| [SETUP.md](SETUP.md) | Rebuilding everything from scratch on a new machine or AWS account |

## Reference

| Document | Contents |
|---|---|
| [SECURITY.md](SECURITY.md) | Threat model, controls with evidence, accepted risks, incident first steps |
| [COST.md](COST.md) | Verified prices, standby and drill costs, actual billing, budget alerts |
| [LESSONS-LEARNED.md](LESSONS-LEARNED.md) | What worked, surprises, **open items in priority order** |
| [DECISIONS.md](DECISIONS.md) | Architecture decision records ADR-001 to ADR-016, and the open-decision log |
| [CHANGELOG.md](CHANGELOG.md) | What changed in each phase |
| [MASTER_BLUEPRINT.md](MASTER_BLUEPRINT.md) | The original requirements (v1.0); the PDF is the unchanged baseline |
| [aws/bayanihandr-developer-inline-policy.json](aws/bayanihandr-developer-inline-policy.json) | The operator permission set's inline policy |

## Component READMEs

| Folder | README |
|---|---|
| `cooperative-system/` | [CMS: run, seed, test](../cooperative-system/README.md) |
| `backend/` | [Backup engine and job runner](../backend/README.md) |
| `terraform/` | [Infrastructure: layout, lifecycles, checks, state](../terraform/README.md) |
| `frontend/` | [Dashboard: modes, scripts, tests](../frontend/README.md) |

## Evidence (timestamped, sanitized)

| Phase | Evidence |
|---|---|
| 4 | [Plan review](evidence/phase4-plan-review.md): real read-only plans, nothing applied |
| 5 | [First deployment](evidence/phase5-deployment.md): pricing, guardrails, inventory, off-site upload and read-back |
| 6 | [First recovery drill](evidence/phase6-recovery-drill.md): RTO 7:15, RPO 19:38 |
| 7 | [Test plan](evidence/phase7-test-plan.md) and [disaster drill report](evidence/phase7-disaster-drill.md): **PASS 10/10**, RTO 5:29, RPO 0:26, corrupted backup refused |
| 10 | [Inventory, destroy-plan review, residual billing](evidence/phase10-inventory.md) |

## Screenshots (public demo, 2026-11-05)

| | |
|---|---|
| ![Overview](screenshots/overview-desktop.png) | ![Backups](screenshots/backups-desktop.png) |
| ![Recovery](screenshots/recovery-desktop.png) | ![Activity](screenshots/activity-desktop.png) |

Phone: [overview-phone.png](screenshots/overview-phone.png). Regenerate with `cd frontend && node scripts/screenshots.mjs`.
