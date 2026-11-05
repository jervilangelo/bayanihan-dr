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

## ADR-009 — Backup engine: snapshot-consistent pg_dump, verify by disposable restore, file-based store

- **Status:** Accepted
- **Date:** 2026-11-04
- **Context:** Phase 3 needs scheduled backups, metadata, checksums, retention, restore verification and failure
  handling, validated locally before any AWS work (blueprint §9).
- **Decision:**
  - Python engine (`backend/bdr_engine`) in a container based on `postgres:16-alpine`, so `pg_dump` and
    `pg_restore` always match the server's major version.
  - Record counts and the schema revision are read in the same exported `REPEATABLE READ` snapshot that
    `pg_dump --snapshot` uses. The manifest then describes the archive exactly.
  - A backup becomes `verified` only after the checksum matches, `pg_restore --list` reads it, it restores into a
    RAM-only disposable PostgreSQL (`verify-db`), and the schema revision and counts match. A checksum alone is not proof.
  - The store is plain files: one directory per backup ID, an atomic `manifest.json`, `events.jsonl`, and
    `status.json`. A `flock` stops jobs from running concurrently.
  - The dashboard reads `status.json` through a dev-server-only route (`npm run dev:ops`). The local provider is
    read-only and is compiled out of the production (GitHub Pages) build.
- **Consequences:** No database or service is needed to track backups, and the same files can be uploaded to S3 in
  Phase 5. Phase 6 replaces the status-file route with an authenticated API.

---

## ADR-010 — Local backup schedule and retention (resolves the local part of OD-4)

- **Status:** Accepted
- **Date:** 2026-11-04
- **Decision:**
  - Hourly on the hour (UTC), and every backup is test-restored immediately.
  - Retention:
    - keep everything for 24 h (so failures stay available for diagnosis);
    - then keep the newest verified backup per UTC day for 7 days;
    - never delete the newest verified backup or an in-progress one.
  - Retention runs after each scheduled backup. The CLI `prune` command defaults to a dry run.
- **Open:** S3 lifecycle and retention, and SSE-S3 versus SSE-KMS. These stay in OD-4 for Phase 5.

---

## ADR-011 — Terraform layout, remote state and recovery access (resolves OD-2 and OD-3)

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision:**
  - Five local modules (networking, compute, storage, identity, monitoring) and one root,
    `environments/recovery`. A `recovery_enabled` switch adds or removes the paid network and compute, while the
    backup bucket and IAM stay in place.
  - **OD-2:** S3 backend with native lockfiles (`use_lockfile`, Terraform ≥ 1.10). There is no DynamoDB table.
    The state bucket comes from a separate `bootstrap/` configuration with local state, applied once in Phase 5,
    with `prevent_destroy` set.
  - **OD-3:** SSM Session Manager. There are no inbound security-group rules, no SSH keys and no bastion. The host
    needs outbound 443 only.
  - No NAT Gateway: the host gets a public IPv4 (about USD 0.005/h) for outbound traffic. S3 traffic goes through
    a free gateway endpoint.
  - Tests run with `terraform test` on a mocked provider, so CI needs no AWS credentials.
- **Consequences:** a real `plan` needs a read-only AWS profile (permission set `BayanihanDR-Developer-V5`, `ReadOnlyAccess`). Teardown has to
  empty the backup bucket on purpose, because `force_destroy` is false.

---

## ADR-012 — Encryption and logging trade-offs accepted for cost (proposes the OD-4 encryption answer)

- **Status:** Accepted by the project owner, 2026-11-05 (Phase 5 apply review).
- **Date:** 2026-11-05
- **Context:** Trivy flags SSE-S3 instead of a customer managed KMS key (AWS-0132, HIGH), log groups without
  a CMK (AWS-0017, LOW) and S3 buckets without access logging (AWS-0089, LOW).
- **Decision:**
  - Use SSE-S3 for the backup and state buckets. A CMK costs about USD 1/month plus requests, which is a large
    share of a PHP 300–500 budget, and the data is synthetic. The storage module switches to SSE-KMS with one
    variable (`kms_key_arn`).
  - Use CloudWatch's default encryption for logs.
  - Do not enable S3 access logging, which needs another bucket. CloudTrail management events record bucket
    configuration changes.
  - Each accepted finding is annotated in place with `#trivy:ignore`, so scans pass but the exception stays visible.
- **Revisit:** if real (non-synthetic) data is ever stored, or if a stricter compliance baseline is needed.

---

## ADR-013 — Off-site upload with an upload-only role and short-lived credentials

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision:**
  - The engine uploads only verified backups, archive first and then manifest, each with `ChecksumSHA256` so S3
    rejects corrupted transfers. Objects go under `backups/<id>/` in the versioned SSE-S3 bucket.
  - It authenticates as `bdr-recovery-backup-writer`. That role allows `s3:PutObject` on `backups/*` only, and
    only the operator SSO role may assume it. Credentials last 1 hour and are passed through the environment,
    never stored.
  - Read-back is verified with the operator role: download, SHA-256 against both manifests, `pg_restore --list`.
- **Consequences:** a compromised office server cannot list, read or delete off-site backups, and versioning keeps
  any overwritten object. Unattended hourly uploads need longer-lived workload credentials (IAM Roles Anywhere
  or similar), which is deferred to Phase 6.

---

## ADR-014 — Recovery job runner and self-reporting recovery host (resolves OD-5)

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision:**
  - **OD-5 (local authentication):** the runner listens on 127.0.0.1 only and requires a random bearer token from
    a git-ignored file, compared in constant time. It also checks the Host header and the Origin, which blocks DNS
    rebinding and cross-site requests. AWS access comes from the operator's SSO session, not from the runner.
    An alternate workstation needs the repository, Terraform, the AWS CLI with SSO access, and `recovery.tfvars`
    plus `backend.hcl`. Nothing on the office server is required.
  - **Workflow:** preflight → `terraform plan` → plan guard → typed approval → apply of the **saved** plan →
    the host restores itself → report. Teardown is a separate job, with a delete-only plan guard and its own approval.
  - **Recovery host:** restores without any inbound access. User data installs Docker, fetches the CMS at a pinned
    commit SHA, downloads the chosen backup, checks its SHA-256 against the verified manifest, restores
    PostgreSQL, starts the CMS, health-checks it and compares record counts. It reports each step as JSON to
    CloudWatch Logs (one stream per job). The database password is generated on the host and never leaves it.
  - **Measurement:** RTO runs from job creation (incident declared) to the host's `recovery-complete` event, so
    approval time counts, as it would in a real disaster. RPO is declared time minus the backup time. The report
    lists approval wait, provisioning and host durations separately.
- **Consequences:**
  - The host's own report is the source of verification. An independent check from outside needs SSM port
    forwarding (available through the operator policy).
  - The host clones the public GitHub repository at a pinned SHA. Publishing the CMS image to a registry (Phase 8)
    would remove the build time from the RTO.

---

## ADR-015 — CI without cloud credentials

- **Status:** Accepted
- **Date:** 2026-11-05
- **Decision:**
  - CI never holds AWS credentials. Infrastructure is checked by static analysis (fmt, validate, TFLint, Trivy)
    and `terraform test` on a mocked provider.
  - `plan` and `apply` stay with the operator and the job runner, behind the plan guard and approval.
  - Workflows default to `contents: read`. Only the Pages deploy job gets `pages: write` and `id-token: write`.
  - Third-party actions are pinned to commit SHAs, with Dependabot proposing updates.
  - Tests run against real PostgreSQL in containers, mirroring local development.
- **Consequences:** a malicious pull request or compromised action cannot reach AWS. Real-plan drift is only caught
  when an operator plans: a scheduled read-only plan through GitHub OIDC is a possible later addition, but it would
  need a dedicated read-only role.

---

## ADR-016 — Keep the standby environment after the project; full teardown documented, not run

- **Status:** Accepted by the project owner
- **Date:** 2026-11-05
- **Decision:**
  - Keep the standby footprint in AWS: the backup and state buckets, two IAM roles, the log group and the budget.
    It costs about USD 0.01/month or less, keeps the off-site recovery points, and lets a drill run again at any time.
  - Every drill environment is torn down; none is running.
  - The full destroy plan was reviewed (15 resources) and recorded in `docs/evidence/phase10-inventory.md`. The
    procedure, including emptying the versioned bucket and removing the state bucket's `prevent_destroy`, is
    RUNBOOK §11.
- **Consequences:** blueprint Phase 10's "approved destroy" is deferred by the owner's decision. The public demo
  works with or without AWS. Re-check billing after 2026-11-06 to confirm the drill charges.

---

## Open decisions (from blueprint v1.0)

| # | Question | Target phase |
|---|---|---|
| OD-1 | ~~HashRouter vs static route fallback for GitHub Pages~~ Resolved by ADR-006 | Phase 2 ✔ |
| OD-2 | ~~Terraform remote-state backend + locking~~ Resolved by ADR-011 | Phase 4 ✔ |
| OD-3 | ~~Recovery access: SSM vs SSH~~ Resolved by ADR-011 (SSM) | Phase 4 ✔ |
| OD-4 | ~~Local schedule/retention, restore-test cadence~~ Resolved by ADR-010. S3 retention (30 d / 7 d noncurrent) in the storage module; SSE-S3 accepted (ADR-012) | Phase 5 ✔ |
| OD-5 | ~~Local authentication; alternate-workstation recovery~~ Resolved by ADR-014 | Phase 6 ✔ |
| OD-6 | ~~Verify current pricing and test budget~~ Verified with the AWS Pricing API (2026-11-05); actual spend ≈ USD 0.01 (docs/COST.md) | Phase 5 ✔ |
