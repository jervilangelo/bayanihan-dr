# BayanihanDR — Master Project Blueprint

**Terraform-Powered Disaster Recovery for Philippine Small Businesses**

| Item | Value |
|---|---|
| Blueprint version | 1.0 (Markdown edition) |
| Original baseline | [`BayanihanDR_Master_Blueprint_v1.0.pdf`](BayanihanDR_Master_Blueprint_v1.0.pdf) — preserved unchanged |
| Repository | https://github.com/jervilangelo/bayanihan-dr |
| Planned public demo | https://jervilangelo.github.io/bayanihan-dr/ |
| Development environment | Windows, VS Code, Claude Code |
| AWS region | `ap-southeast-1` (Singapore) |
| Document status | Baseline plan. Implementation details and cost estimates are **not** verified results. |
| Prepared | 04 November 2026 |

> **Sources.** This Markdown file transcribes every substantive requirement in the v1.0 PDF and folds in the
> more detailed requirements from the master development prompt (dashboard pages, animations, Terraform
> requirements, security, phase tasks). Where the prompt adds detail beyond the PDF, it is marked _(prompt)_.
> Nothing here conflicts with the PDF.

---

## 0. Document Control

| Item | Policy |
|---|---|
| Purpose | Single source of truth for project scope, architecture, phases, controls, decisions, and acceptance criteria. |
| Change management | Update this blueprint and [`CHANGELOG.md`](CHANGELOG.md) when architecture or scope changes. Preserve version history. Record architectural decisions in [`DECISIONS.md`](DECISIONS.md). |
| Source of truth | This file (`docs/MASTER_BLUEPRINT.md`) is the living, editable source of truth. The PDF is a readable snapshot. New versioned PDFs are proposed at major milestones. |
| Authority | The blueprint guides development but **never** authorizes AWS charges, destructive actions, or publication without explicit approval from the project owner. |
| Material changes | Before a material architectural change, explain the reason and request approval. Record approved changes in the change log and decision log. |

---

## 1. Project Overview and Executive Summary

BayanihanDR is a low-cost disaster recovery (DR) proof of concept for a fictional agricultural cooperative in Naga
City, Camarines Sur. The cooperative depends on a local Cooperative Management System (CMS). A typhoon, flood, or
prolonged power failure can make the primary Linux server unavailable. BayanihanDR protects verified PostgreSQL
backups off-site, provisions temporary AWS recovery infrastructure using Terraform, restores the CMS, validates its
health, and records measurable recovery outcomes.

The project has two deliverables:

1. A **real, reproducible technical disaster recovery workflow**.
2. A **friendly, polished web dashboard** that stays publicly accessible as a safe demonstration after AWS test
   resources are destroyed.

It is not a purely visual simulation: the finished project must demonstrate actual backup and recovery. _(prompt)_

It is a portfolio project for Junior Cloud Engineer, Cloud Infrastructure Engineer, and DevOps Engineer roles.
It must stay simple enough to understand, maintain, and explain in a technical interview. _(prompt)_

### Success criteria

- A synthetic-data CMS works locally with PostgreSQL and Docker Compose.
- Backups are generated, checksummed, tested through restore, and securely stored off-site.
- Terraform can provision the approved AWS recovery environment reproducibly.
- A recovery drill restores the application and validates expected records.
- Actual RTO/RPO measurements and cost evidence are documented. Targets are not presented as achieved until tested.
- A responsive GitHub Pages demo remains usable without a running AWS backend.
- Temporary billable resources are reviewed and removed after approved testing.

---

## 2. Business Problem and Scenario

### 2.1 Fictional organization

**Bicol Farmers Cooperative (BFC)**, Naga City, Camarines Sur, Philippines.

- About 25 employees
- More than 1,000 farmer members
- Limited IT budget
- Small internal IT team
- Runs a locally hosted business application, the Cooperative Management System (CMS)

### 2.2 Cooperative Management System

The CMS stores:

- Farmer membership records
- Agricultural inventory
- Sales transactions
- Cooperative contributions
- Operational reports

The primary application runs locally using Docker, FastAPI, and PostgreSQL. **All application records used in this
project are synthetic.**

### 2.3 Disaster scenario

A severe typhoon causes flooding and an extended power outage. The primary office and local server become
inaccessible. The cooperative cannot reach its membership, inventory, and transaction records, and on-site backups
may also be inaccessible. The recovery administrator operates from **another trusted device and network**. The
original office must not be required to start the recovery.

### 2.4 Proposed solution _(prompt)_

1. Create scheduled database backups.
2. Verify backup integrity.
3. Store recoverable backups in encrypted Amazon S3.
4. Provision AWS recovery infrastructure using Terraform.
5. Restore the CMS database.
6. Start the CMS application in AWS.
7. Validate restored application functionality.
8. Measure actual recovery performance.
9. Display operational information through a web dashboard.
10. Safely destroy temporary recovery infrastructure after testing.

---

## 3. Project Objectives

### 3.1 Primary objective

Build a working, low-cost disaster recovery proof of concept that shows how a Philippine small business can recover
its essential application after losing access to its primary server.

### 3.2 Technical objectives _(prompt)_

Demonstrate Infrastructure as Code, AWS networking, Linux administration, EC2 provisioning, IAM security, S3 backup
storage, PostgreSQL backup and restore, Python automation, Docker containerization, DR orchestration, cloud
monitoring, CI/CD, automated testing, frontend development, and infrastructure cost management.

---

## 4. Scope and Exclusions

### In scope

- Local CMS API, PostgreSQL schema and migrations, seed data, and basic health checks.
- Scheduled database backups, integrity checks, recovery-point inventory, retention, and restore verification.
- S3 storage with encryption, restricted access, and suitable retention and versioning decisions.
- Terraform modules for networking, compute, storage, IAM, and monitoring.
- A controlled recovery orchestrator and local operations dashboard.
- Recovery testing, CI/CD checks, GitHub Pages portfolio mode, runbooks, and cleanup.

### Out of scope for v1

- Real farmer or financial data; production service-level guarantees; 24/7 hosted commercial operations.
- Multi-region active-active architecture, managed database clusters, payment processing, and complex multi-tenant
  authorization.
- Public execution of Terraform, a public operational backend, and continuous paid AWS standby infrastructure.

---

## 5. RTO and RPO Targets

| Metric | Target / definition |
|---|---|
| **RTO** | **30-minute target**, measured from the declared disaster/recovery start to verified CMS availability. Document the exact stopwatch boundary. |
| **RPO** | **1-hour target**, measured as the time between the disaster event and the latest successfully restorable data point. |
| Backup frequency | Hourly, as a design target only once scheduling, verification, and end-to-end restore prove it. |
| Evidence | Timestamped backup manifests, logs, restore checks, health checks, recorded elapsed time, and AWS usage/cost records. |

- These are **design targets, not guaranteed results**. Define the measurement boundaries before testing.
- A successful restore from a backup does not by itself prove a 1-hour RPO. Scheduling, backup completion,
  verification, clock consistency, and disaster timing all matter.
- Test missed or corrupt backups and report limitations.
- Never report target values as achieved without evidence.

Phase 7 must measure: provisioning duration, database restore duration, application startup duration, total
recovery time, backup age, recovery success, and AWS costs. _(prompt)_

---

## 6. Architecture

BayanihanDR has three systems _(prompt)_:

### 6.1 System A — Primary Cooperative Management System (local)

A local Docker Compose stack runs the CMS API (FastAPI) and PostgreSQL, with basic business features. It represents
the cooperative's primary infrastructure. A backup job produces a consistent database dump and a metadata manifest,
verifies checksums, and periodically runs test restores. Backup copies are uploaded securely to S3.

To simulate the disaster, this application is **intentionally stopped**. Source data is never destroyed to simulate
a disaster.

### 6.2 System B — BayanihanDR Recovery Engine

Manages backup execution, backup verification, backup metadata, S3 uploads, recovery-point selection, Terraform
orchestration, restore execution, health checks, recovery event logging, and RTO/RPO measurement.

- It must be able to run from a **separate trusted computer** if the primary server is unavailable. Recovery must not
  depend on the failed primary server.
- It must not expose unrestricted shell execution or Terraform commands.

**Recovery environment:** a trusted recovery operator uses a separately available workstation with AWS access and
protected Terraform state. Terraform provisions an isolated AWS network and a temporary EC2 Linux host. Bootstrap
scripts configure Docker or the application dependencies, fetch the approved backup, restore PostgreSQL, start the
CMS, and run health and record checks.

### 6.3 System C — BayanihanDR Dashboard

A React/Vite dashboard with two modes:

- **Local operational mode:** connects to the authenticated FastAPI recovery backend and supports authorized
  operational actions.
- **Public portfolio mode** (GitHub Pages): uses sanitized static JSON. It shows historical recovery results,
  sanitized logs, recovery workflow demonstrations, architecture information, recorded performance metrics, and
  project information. It is read-only or simulation-only and must **never** call real recovery endpoints, expose
  credentials, or offer privileged actions. It must work without an active AWS backend.

A **typed provider interface** swaps mock data for real data without rewriting pages.

### 6.4 Conceptual data flow

```
Local CMS + PostgreSQL
  -> scheduled backup + checksum + restore test
  -> encrypted S3 backup
  -> approved recovery orchestration
  -> Terraform EC2 environment
  -> restore and verify
  -> evidence and metrics
  -> sanitized public demo
```

### 6.5 Key failure-domain requirement

Backup copies, recovery credentials, Terraform state, and recovery instructions must stay usable if the primary office
and server are lost. A local-only orchestration service is a convenience, not the only recovery path.

---

## 7. Technology Stack

| Area | Preferred choice | Reason |
|---|---|---|
| Frontend | React, Vite, TypeScript, Tailwind CSS | Static GitHub Pages deployment, typed interfaces, low operating cost. |
| Motion | Motion for React | Smooth, restrained transitions; reduced-motion support. |
| UI | TasteSkill, UI/UX Pro Max, selective shadcn/ui, Lucide icons | Distinctive visual system without a generic template look. |
| Charts | Recharts when needed | Useful backup/recovery trends, not decorative analytics. |
| CMS | FastAPI + PostgreSQL + Docker Compose (+ migrations, synthetic seed data) | Practical Linux/database recovery exercise. |
| Operations API | Python FastAPI + Pydantic + optional SQLite metadata, structured logging, background jobs | Controlled local jobs, audit trail, API contracts. |
| IaC | Terraform + official HashiCorp skills | Reusable, reviewable infrastructure; portfolio relevance. |
| AWS | VPC, EC2, EBS, S3, IAM, CloudWatch, optional Systems Manager (SSM) | Low-complexity cold recovery infrastructure. |
| CI/CD | Git, GitHub, GitHub Actions, pytest, Terraform validation, TypeScript checks, Playwright | Repeatable tests and static frontend publication. |

---

## 8. Terraform Design and AWS Infrastructure

### 8.1 Module boundaries

| Module | Resources / concerns |
|---|---|
| `networking` | VPC, public subnet, Internet Gateway, route table, restrictive security groups. Minimal; no unnecessary networking components. |
| `compute` | Small temporary EC2 Linux instance, user data/bootstrap, EBS volume, instance profile. Validate instance-type availability and expected cost before deployment. |
| `storage` | Encrypted S3 backup bucket, versioning and retention decisions, restricted bucket policy, protection against accidental deletion. |
| `identity` | Least-privilege IAM roles and policies; no long-lived credentials in source. |
| `monitoring` | CloudWatch log groups, basic application health monitoring, recovery operation logs, alerts only where justified; bounded retention. |

### 8.2 Terraform requirements

Reusable modules, variables, outputs, locals, version constraints (Terraform and providers), resource tagging,
environment-specific configuration (`terraform/environments/recovery/`), protected state management, state locking,
validation and testing, and documented module interfaces. Recovery infrastructure must be reproducible.

### 8.3 State and bootstrap

Use **protected remote Terraform state** with locking supported by the chosen backend and tooling version. The state
backend must exist independently of the primary site and be created through an explicit, separately reviewed
bootstrap process. Never commit state or secrets. Document the bootstrap process and disaster access.

### 8.4 Network and access

- Prefer **SSM Session Manager** where practical. Otherwise, restrict SSH tightly to an approved IP and use
  short-lived credentials.
- No public database exposure.
- A public IPv4 address, EBS, S3 requests, logs, and data transfer may incur costs.
- No NAT Gateway, RDS, ALB, EKS, or always-on paid services in v1 unless separately approved.

### 8.5 Validation and review

Use `terraform fmt`, `validate`, `plan`, lint and security scanning where available. **Never run `terraform apply` or
`destroy` without explicit user approval.**

---

## 9. Backup Strategy

1. Create a consistent PostgreSQL backup using `pg_dump` or an equivalent supported procedure.
2. Generate a manifest: backup ID, UTC timestamp, source version, schema/app version, size, checksum, and
   verification state.
3. Validate the archive and periodically restore it into a disposable PostgreSQL instance. A checksum alone does not
   prove the data is restorable, and neither does a successful upload.
4. Encrypt backup objects in S3, enforce least-privilege access, and set retention and deletion safeguards.
5. Manage retention.
6. Track schedule failures, upload failures, missing backups, and stale verification. **Never mark unverified backups
   as protected.**
7. Report backup status to the dashboard.

Validate the workflow locally first.

## 10. Disaster Recovery Strategy

### 10.1 Recovery sequence

1. Declare the incident and confirm the primary is unavailable; **start the RTO timer**.
2. Confirm independent access to backup storage, AWS credentials, Terraform state, and the runbook.
3. Select the latest verified, compatible recovery point; review the plan and expected cost.
4. Approve the job explicitly; block duplicate concurrent jobs.
5. Provision (or verify) the approved recovery infrastructure; bootstrap the application environment.
6. Download and verify the selected backup; restore the database and start the CMS.
7. Run health checks and verify known records and expected application behavior.
8. Record RTO, RPO, timestamps, outcomes, logs, and any exceptions; produce a recovery report.
9. Preserve evidence and get separate approval for teardown.

### 10.2 Failure handling

**Fail closed** if backup integrity fails, authentication is missing, state is locked, a job is already running, or
estimated actions differ from the reviewed plan. Preserve diagnostics and give safe retry guidance.

### 10.3 Recovery engine safety

Authenticated administrator access, controlled (allowlisted) operations, recovery job IDs, job state tracking,
structured logs, timeouts, error handling, duplicate-job protection, and audit records. No unrestricted command
execution. The public GitHub Pages deployment can never start real AWS recovery operations.

---

## 11. Security Requirements

1. Use synthetic cooperative data only: no real personal, payroll, membership, financial, farmer, or employee data.
2. Never commit `.env` credentials, access keys, private keys, backup contents, Terraform state, or privileged
   endpoint URLs. Never hardcode AWS credentials.
3. Use short-lived or role-based AWS authentication where possible, least-privilege IAM, encryption in transit and
   at rest, and explicit credential rotation procedures.
4. Separate public demo assets from operational data. Sanitize logs, account IDs, IPs, secrets, and internal paths
   before publishing.
5. Local recovery operations require authenticated administrator access, authorization checks, CSRF/origin
   protections where relevant, allowlisted job types, and auditable approvals.
6. Never accept arbitrary shell commands or Terraform arguments from browser input.
7. Keep operations available from a trusted alternate workstation after primary-site loss; protect recovery
   credentials independently of the primary server.
8. Record resource creation, approval, recovery, and destruction in an audit trail.
9. Review dependencies and third-party skills before trusting them with credentials. _(prompt)_

---

## 12. Dashboard Design

**Audience:** non-technical small-business administrators and technical recovery operators.
**Design principle:** answer "Are we protected?" and "What should we do next?" clearly, without burying the user in
AWS terminology.

### 12.1 Visual language

- Light theme by default. Suggested palette: background `#F8FAF9` (warm off-white), primary `#397D6A` (sage),
  secondary `#DCEDE7` (pale green), accent `#7DA8C7` (soft blue), text `#263B36` (charcoal), warning `#D9A441` (gold).
  TasteSkill and UI/UX Pro Max may refine it.
- Custom layout and information hierarchy; refined typography, generous whitespace, soft backgrounds, subtle borders,
  minimal shadows, meaningful status labels, purposeful data visualization, responsive layouts.
- **Avoid:** repetitive KPI cards, excessive rounded boxes, generic SaaS templates, overcrowded sidebars, unnecessary
  or decorative charts, gradients, clutter, flashy dashboards, cyberpunk/dark styling, purposeless animation,
  overwhelming technical terminology. Build a recognizable BayanihanDR identity.
- Accessible contrast, keyboard navigation, focus indicators, responsive layout, readable failure states.

### 12.2 Pages

| Page | User-facing capabilities |
|---|---|
| Overview | Primary server status, last verified backup, recovery readiness, target RTO, recent activity, clear next (recovery) action. |
| Backups | Backup list/history, size and time, verification status, checksum/metadata summary, selectable recovery points. |
| Recovery | Preflight readiness checklist, recovery point selection, plan preview, explicit approval, step-by-step progress, verification, result. |
| Activity | Chronological backup, infrastructure, recovery, warning, error, and audit events, with filters. |
| Settings | Recovery targets, safe preferences, environment/region information; privileged configuration only in local mode. |

### 12.3 Demo mode _(prompt)_

An interactive demo lets users navigate, inspect backups, select a recovery point, run a **clearly labeled simulated
recovery**, watch progress, view simulated results, and browse activity history. The simulation must never invoke
AWS or Terraform.

## 13. Animation Requirements

- Motion for React. Typical transitions are 150–300 ms.
- Smooth page transitions, subtle staggered entrances, refined hover interactions, animated recovery progress steps,
  backup timeline transitions, polished loading states and skeletons, accessible feedback animations.
- Support `prefers-reduced-motion`.
- Animations must never interfere with critical recovery operations.

---

## 14. Development Phases

Every phase ends with working deliverables and **stops for user approval** before the next phase.

| Phase | Build | Exit gate |
|---|---|---|
| **0 — Blueprint and environment** | Authoritative Markdown blueprint + PDF snapshot; change and decision logs; inspect tools, skills, repository, architecture; project structure; acceptance criteria. | Blueprint saved, reviewed, versioned; no AWS resources. |
| **1 — Local cooperative CMS** | Docker Compose, FastAPI, PostgreSQL, migrations, synthetic farmer/inventory/transaction data, CRUD and health endpoints, automated tests. | Local app runs; API and DB tests pass. |
| **2 — Dashboard and animations** | React/Vite five pages, distinctive UI system, mock provider, recovery simulation, accessibility and Playwright checks. | Five pages work; simulation clearly labeled; build/tests pass. |
| **3 — Backup and restore** | Scheduled `pg_dump`, metadata, checksums, retention, local restore verification, failure handling; backup status in the dashboard. | Repeatable successful restore; bad backups detected. |
| **4 — Terraform infrastructure** | Modules for networking, compute, S3, IAM, CloudWatch; remote-state plan; fmt/validate/plan. | Reviewed, valid plan; **no apply**. |
| **5 — Approved AWS integration** | Review plan, estimate cost, verify billing alerts, review security and cleanup; explicit apply approval; deploy, upload verified backups, verify access; record deployed resources. | Resource inventory and verified AWS backups. |
| **6 — Recovery orchestration** | Authenticated FastAPI job runner, bounded Terraform workflow, backup selection, restore and checks, audit events; real data in the local dashboard. | Controlled recovery job succeeds with audit evidence. |
| **7 — Disaster drill and metrics** | Stop the primary CMS, restore from a trusted alternate context, verify data, measure RTO/RPO and cost; recovery test report. | Timestamped evidence and an honest pass/fail report. |
| **8 — CI/CD and quality** | GitHub Actions: Terraform fmt/validate/security, Python tests, TypeScript checks, frontend build, Playwright, Pages deployment; least-privilege permissions. | Pipelines pass without unapproved AWS provisioning. |
| **9 — GitHub Pages publication** | Safe static demo with sanitized recorded results, Vite `base: '/bayanihan-dr/'`, Pages-compatible routing (direct navigation and refresh work); Playwright tests of the public site. | Public site works while AWS is offline. |
| **10 — Documentation and teardown** | README, architecture diagram, Terraform docs, runbook, recovery test report, cost breakdown, security docs, screenshots, lessons learned, reproduction steps; inventory, evidence preservation, destroy-plan review, approved destroy, residual billing check. | Docs complete, public demo persists, residual charges checked. |

### Per-phase implementation rules _(prompt)_

Read the relevant blueprint sections, identify skills, inspect existing files, write a short plan, write working
code, run tests, fix issues, review security and cost, update docs, and summarize. Every phase report covers: features
implemented, files changed, tests run and their results, skills used, AWS resources created, estimated charges, known
limitations, and the next milestone. Never claim functionality works unless it was verified.

### Skill-to-phase mapping

| Skill | Use |
|---|---|
| HashiCorp Terraform plugin | Phases 0, 4, 5, 6, 8, 10: module conventions, state, testing, lifecycle. |
| Superpowers | All phases: architecture, decomposition, test-first work, debugging, review, verification. |
| TasteSkill | Phases 2 and 9: custom visual language, composition, interaction polish. |
| UI/UX Pro Max | Phases 2 and 9: usability, accessibility, responsive patterns. |
| Playwright CLI | Phases 2, 7, 8, 9: browser behavior, responsive and visual checks. |

Verify each installed skill and read its actual instructions before claiming to use it. Report missing or
incompatible skills; never invent them.

---

## 15. Testing Strategy

### Unit and integration
- CMS CRUD, validation, migrations, and health endpoint tests.
- Backup script error handling, manifest/checksum generation, and restore verification tests.
- Recovery job state machine, authorization, concurrency, and retry behavior tests.
- Frontend provider contracts, navigation, loading/error states, and demo simulation tests.

### End-to-end and operations
- Playwright across desktop and mobile sizes, and with the reduced-motion setting.
- Terraform formatting, validation, a reviewable plan, and security checks.
- A controlled disaster drill with known synthetic records and timestamped verification.
- Public site verification after AWS resources are destroyed.

### Evidence
Store sanitized screenshots, logs, test outputs, measured durations, backup manifest examples, infrastructure
diagrams, and cost observations. Never fabricate data or claim targets were met without proof.

---

## 16. Cost Controls

Target total test spending: **PHP 300–500**. This is a planning budget, **not a hard cap or a verified quote**.
Recalculate against current `ap-southeast-1` pricing and actual instance runtime before any apply.

| Cost driver | Control |
|---|---|
| EC2 runtime | Small compatible instance, run only during approved recovery drills, stop/terminate promptly. |
| EBS | Keep volumes minimal; verify cleanup of detached volumes and snapshots. |
| Public IPv4 | Include the hourly address cost if one is assigned; avoid unused Elastic IPs. |
| S3 | Small synthetic backups; review lifecycle/retention and versioning carefully. |
| CloudWatch | Short log retention; avoid high-frequency custom metrics. |
| Data transfer / requests | Estimate backup uploads, downloads, API calls, and cross-region traffic. |
| State storage | Include any ongoing state-backend storage/locking cost after teardown. |

- Avoid NAT Gateways, RDS, ALBs, EKS, and unnecessary always-on resources unless explicitly approved.
- Configure AWS billing alerts before deployment. **Billing alerts do not stop charges.**
- Record the baseline resource inventory, pre-deployment plan, runtime duration, and post-destroy inventory.
- Never create paid resources without approval.

---

## 17. GitHub Deployment Strategy

- Repository: https://github.com/jervilangelo/bayanihan-dr. Public URL: https://jervilangelo.github.io/bayanihan-dr/
- Vite `base: '/bayanihan-dr/'`. Use GitHub Pages-compatible routing and verify direct navigation and refresh.
- Workflows: frontend lint/typecheck/build and browser tests; publish static artifacts to Pages after approval;
  backend pytest and static checks; Terraform fmt, validate, and security checks.
- **No automatic Terraform apply or destroy on ordinary pushes.** Least-privilege GitHub Actions permissions; review
  deployment environments and branch protection.
- Meaningful commits; clean repository. **Never push or publish without explicit approval.**
- The public dashboard must keep working after AWS infrastructure is destroyed.

### Repository layout

```text
bayanihan-dr/
├── frontend/                 # public dashboard + provider interfaces
├── backend/                  # local recovery API (System B)
├── cooperative-system/       # CMS + database (System A)
│   ├── app/
│   ├── migrations/
│   └── tests/
├── terraform/
│   ├── modules/{networking,compute,storage,identity,monitoring}/
│   └── environments/recovery/
├── scripts/{backup,restore,validation}/
├── tests/
├── docs/
├── .github/workflows/
├── README.md
└── .gitignore
```

Directories are created when the phase that needs them begins; no empty placeholder directories.

---

## 18. Documentation Requirements

Professional README (updated at major milestones), architecture diagram and `docs/architecture.md`, Terraform
documentation, DR runbook (`docs/recovery-runbook.md`), recovery test report (`docs/recovery-test-report.md`), AWS
cost breakdown (`docs/cost-estimate.md`), security documentation, screenshots, lessons learned, and reproduction
instructions. Preserve actual evidence from successful tests.

---

## 19. Acceptance Criteria (Definition of Done)

- All required code is committed to the authorized repository, with no secrets.
- The CMS, backups, Terraform deployment, and recovery drill are reproducible from the documentation.
- Measured recovery performance, failure cases, and actual AWS costs are recorded.
- The dashboard works both as a safe static portfolio demo and as a controlled local operations UI.
- Automated tests and accessibility checks pass, or their limitations are documented.
- AWS resources are destroyed only after explicit approval, and residual charges are reviewed.
- The blueprint is updated for every material architecture, scope, cost, or workflow change.

---

## 20. Risks and Limitations

| Risk | Mitigation |
|---|---|
| Unexpected AWS charges | Preflight estimates, short-lived resources, billing alerts, explicit apply/destroy approval, post-test inventory. |
| Primary-site loss blocks recovery | Independent backup access, remote state, runbook, alternate trusted workstation. |
| Unrestorable backups | Scheduled disposable restore tests, checksums, manifests, compatible versions. |
| Secrets exposed publicly | Separate builds, sanitized static data, secret scanning, no public privileged APIs. |
| Insecure recovery automation | Authentication, allowlisted actions, plan review, job locks, audit trail. |
| Overbuilt UI delays infrastructure | Five-page scope, purposeful animations, functional demo first. |
| RTO/RPO missed | Measure honestly, isolate slow steps, improve and rerun; no fabricated compliance. |
| Windows/toolchain incompatibility | Inspect versions, Docker availability, long-path support; document workarounds. |

**Known limitations (v1):** a cold-standby proof of concept, not a production DR service. There are no SLA
guarantees, no multi-region redundancy, and no managed database. All data is synthetic.

---

## 21. Open Decisions

Tracked in [`DECISIONS.md`](DECISIONS.md). Open from the v1.0 baseline:

- ~~HashRouter or a static route fallback for GitHub Pages.~~ **Decided: hash routing (ADR-006).**
- Terraform remote-state backend and locking strategy; document bootstrap and residual costs.
- Recovery access method (SSM preferred where practical; otherwise restricted SSH).
- Backup schedule and retention, encryption key management, and restore-test cadence.
- Exact local authentication method and how alternate-workstation recovery is started.
- Current AWS pricing and the final test budget, verified before provisioning.

## 22. Future Improvements

Candidates after v1, each needing separate approval: warm-standby option with a pre-built AMI to shorten RTO;
point-in-time recovery using WAL archiving (finer RPO); cross-region backup replication; automated scheduled
recovery drills; SNS/email alerting for stale backups; a multi-cooperative (multi-tenant) model.

---

## Change Log

See [`CHANGELOG.md`](CHANGELOG.md).

| Version | Date | Change |
|---|---|---|
| 1.0 | 2026-11-04 | Initial comprehensive blueprint; proposed architecture and phased delivery. |
