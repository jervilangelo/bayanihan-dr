# Changelog

All notable changes to the BayanihanDR blueprint and project are recorded here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Blueprint versions track
`docs/MASTER_BLUEPRINT.md`. The v1.0 PDF is preserved unchanged as the original baseline.

## [Unreleased]

### Added (Phase 10): documentation and teardown review
- `docs/README.md`: an index of all documentation, evidence and screenshots.
- `docs/ARCHITECTURE.md`: the three systems, a component diagram, backup and recovery sequence diagrams, trust
  boundaries, failure domains, data stores and a repository map.
- `docs/RUNBOOK.md`:
  - names and places;
  - daily check, backups and off-site copies, runner and dashboard;
  - drills, **real disaster recovery**, teardown, alternate workstation, host inspection;
  - a troubleshooting table, full project teardown, credential rotation.
- `docs/SETUP.md`: rebuild from scratch, step by step, from tools to the first drill.
- `docs/SECURITY.md`: threat model with controls and evidence, accepted risks, open items, incident first steps.
- `docs/COST.md`: verified prices, standby and drill costs, actual drills, Cost Explorer records, cost risks.
- `docs/LESSONS-LEARNED.md`: what worked, surprises, measured results, open items in priority order.
- `docs/evidence/phase10-inventory.md`: AWS inventory verified with `describe-*` calls, the reviewed destroy plan
  (15 resources, not applied), residual billing.
- `docs/screenshots/` of the live site, and `frontend/scripts/screenshots.mjs` to regenerate them.
- Root README rewritten: status, measured results, how it works, security in brief, quick start, test inventory.
- ADR-016 (keep standby; teardown documented); OD-6 resolved (pricing verified).

### Added (Phase 9): public site with recorded results
- Overview now shows **"Measured in real AWS drills"**, with sanitized results from the Phase 7 and Phase 6 drills:
  RTO and RPO against targets, a breakdown of where the recovery time went, records restored, verification
  method, compute cost and links to the evidence. It is labelled "Recorded results, not simulated". The RTO figure
  now reads "Measured 05:29 in a real drill".
- `src/data/recorded-drills.ts` with a test that blocks account IDs, IPs, instance IDs, bucket names, e-mails and
  ARNs, and checks that stage durations add up to each measured RTO.
- `e2e-public/` + `playwright.public.config.ts` (`npm run test:public`): Playwright against the **live** site.
  Checks direct links and refresh on every page, no external or AWS requests, no HTTP errors or console errors,
  the published results, the full simulation, and that no operational code is in the bundle.
- `.github/workflows/public-site.yml` runs those checks after each Pages deployment and weekly.
- Live-site results: 16/16 passed locally against https://jervilangelo.github.io/bayanihan-dr/ (desktop and phone),
  and the workflow passed after deployment.

### Fixed (Phase 9)
- A race in the e2e test "simulated recovery runs end to end": on fast Linux CI the outgoing Recovery page was
  still fading out when the test searched for text it shares with the Activity page. Reproduced in the CI
  Playwright image; 100/100 passes with every test run twice after the fix.

### Added (Phase 8): CI/CD
- `.github/workflows/ci.yml` runs on every push and pull request.
  - **Dashboard:** typecheck, 36 unit tests, production build, 48 Playwright e2e tests, and a check that no
    job-runner code reaches the Pages bundle.
  - **CMS and backup engine:** tests against real PostgreSQL 16 through docker compose.
  - **Job runner:** 20 tests.
  - **Terraform:** fmt, validate, 16 `terraform test` runs on a mocked provider, TFLint with the AWS ruleset,
    Trivy, and ShellCheck of the rendered recovery-host script.
  - First run (commit `4d7fcbd`): all 4 jobs passed, in 17–73 s each.
- Least privilege: `contents: read` only, no secrets or AWS credentials, every action pinned to a commit SHA,
  `persist-credentials: false`. The Pages workflow is pinned the same way.
- `.github/dependabot.yml`: weekly grouped updates for actions, npm, pip and Docker base images.
- `scripts/validation/render_bootstrap.py` renders the EC2 user-data template for linting.
- ADR-015 (CI design).

### Added (Phase 7): disaster drill and recovery test report
- `docs/evidence/phase7-test-plan.md`: scenario, procedure, measurement boundaries and pass criteria, written
  before the drill.
- `docs/evidence/phase7-disaster-drill.md`: **PASS, 10 of 10 criteria.**
  - Primary stopped; recovered from a fresh clone of the repository acting as the alternate workstation.
  - **RTO 5 min 29 s**, independently verified through an SSM port forward; **RPO 26 s**.
  - The marker before the backup survived and the marker after it was lost, as the RPO predicts.
  - A corrupted off-site backup was refused at the checksum.
  - Teardown left nothing behind; cost about USD 0.007.
  - Limitations stated, chief among them that off-site upload is still manual, so the real RPO depends on the operator.

### Added (Phase 6): recovery orchestration and the first real drill
- `backend/bdr_runner`: the authenticated local job runner.
  - FastAPI on 127.0.0.1, bearer token, Host and Origin checks.
  - Two job types (recovery drill, teardown), one active job at a time, an audit log, and recovery of
    interrupted jobs on restart.
  - Preflight → Terraform plan → plan guard (fail closed) → typed approval → apply of the saved plan → host
    progress from CloudWatch Logs → RTO/RPO report.
  - 20 tests.
- Recovery host user data (`modules/compute/templates/bootstrap.sh.tftpl`): installs Docker, fetches the CMS at a
  pinned SHA, checks the backup's SHA-256 against the manifest, restores PostgreSQL, starts the CMS, health-checks
  it and compares record counts, reporting each step as JSON to CloudWatch Logs. Passes ShellCheck.
- Terraform: `recovery_job_id` and `app_git_ref` inputs; a pinned commit SHA is required (16 tests).
- Dashboard operations mode:
  - a real Recovery page (token sign-in, off-site recovery points, plan review with cost, typed approval,
    live step timeline, measured RTO/RPO, teardown);
  - a dev-only proxy to the runner;
  - the page is lazy-loaded only in dev, so the Pages bundle contains no runner code;
  - 5 new unit tests (36 in total).
- **First real drill** (`docs/evidence/phase6-recovery-drill.md`): CMS recovered and verified in AWS. RTO 7.2 min,
  RPO 19.6 min, records 1050/26/3001 matched. Torn down afterwards, with nothing left running. Cost about USD 0.004.
- ADR-014 (job runner and self-reporting host; resolves OD-5).

### Changed (Phase 6)
- `E2E_PORT` overrides the Playwright preview port (4174 was taken by another local project).
- Operations-mode banner and Settings now reflect that drills can reach AWS after approval.

### Added (Phase 5): first AWS deployment, approved by the project owner
- Applied `terraform/bootstrap`: the state bucket, 7 resources. Its state was then migrated into the bucket.
- Applied `terraform/environments/recovery` in standby, 13 resources: backup bucket, recovery-host role,
  log group, and a USD 10/month AWS Budgets alert. No EC2 or VPC.
- Applied the upload-only `bdr-recovery-backup-writer` role (2 resources).
- `bdr_engine upload`: copies only verified backups off-site, with S3-checked SHA-256 and the version ID
  recorded; failures are recorded as rejected. 6 new tests (41 in total).
- Compose passes `BDR_OFFSITE_BUCKET` and short-lived AWS credentials through to the backup service; the image
  adds boto3.
- Evidence (`docs/evidence/phase5-deployment.md`): pricing checked with the AWS Pricing API, guardrails checked
  with the IAM simulator, an inventory verified with the AWS CLI, and two backups uploaded and read back
  (SHA-256 and `pg_restore` OK).
- ADR-012 accepted (SSE-S3). ADR-013 (off-site upload design).

### Added (Phase 4)
- `terraform/`: AWS infrastructure code. **Nothing is applied.**
  - Modules: `networking`, `compute`, `storage`, `identity`, `monitoring`.
  - Root: `environments/recovery`, with a `recovery_enabled` switch.
  - `bootstrap/` for the remote-state bucket.
  - Choices: S3 native state locking, SSM access with no inbound rules, IMDSv2, encrypted gp3, capped T3 credits,
    no NAT, RDS or load balancer, an upload-only backup-writer role, and an optional AWS Budgets alert.
- 15 `terraform test` runs on a mocked provider (no credentials). They cover the default footprint, the drill
  footprint, input validation, host hardening, network isolation, bucket protection, IAM with no delete
  permissions, and log retention.
- TFLint (AWS ruleset) and Trivy configuration; accepted findings are annotated.
- Provider lock files for Windows, Linux and macOS.
- `.gitattributes` keeps shell scripts and templates LF-only.
- ADR-011 (layout, state, SSM; resolves OD-2 and OD-3) and ADR-012 (encryption and logging trade-offs, proposed).
- `docs/evidence/phase4-plan-review.md`: real read-only plans against the AWS account (standby 12 resources, drill
  24, nothing applied), signed in with the `BayanihanDR-Developer-V5` permission set (`ReadOnlyAccess`).
- `docs/aws/bayanihandr-developer-inline-policy.json`: a project-scoped inline policy for the developer permission
  set, for the one-week build. It allows writes only to `bayanihandr-*` and `bdr-*` resources in ap-southeast-1,
  and denies NAT gateways, Elastic IPs, RDS, load balancers, EKS, IAM users and access keys, and other regions.
  Validated with IAM Access Analyzer (0 findings). Delete it with the permission set after the project.

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
