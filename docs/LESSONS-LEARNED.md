# Lessons learned and open items

Written at the end of the build (Phase 10, 2026-11-05). What worked, what surprised us, and what to do next.

## What worked well

1. **Verify by restoring, not by checksum.** Every local backup is restored into a throwaway database and recounted.
   The Phase 7 corruption test showed why the second layer matters: the archive *looked* fine to S3 (its own
   checksum matched the new object), but it did not match the **verified manifest**, and the host refused it.
2. **One snapshot for the dump and the counts.** Sharing a `REPEATABLE READ` snapshot with `pg_dump --snapshot`
   made "record counts match" an exact test, not an approximate one, even while the CMS keeps writing.
3. **Standby by default, a single switch for drills.** `recovery_enabled` keeps idle cost near zero, and one guarded
   plan adds the drill footprint. Every drill cost well under one US cent.
4. **Plan guard plus saved-plan apply.** Approving a summary of exactly what will be created, then applying that same
   plan file, made the approval meaningful. The guard is simple (allowed address prefixes and actions) and fails
   closed.
5. **The host reports outward.** CloudWatch Logs events from user data meant no inbound access, no SSH and no new
   permissions, yet full step-by-step visibility and timings.
6. **Recover from a fresh clone.** Phase 7 proved that the office server is not needed. Only the repository, S3, the
   state bucket, an SSO sign-in and two small settings files are.
7. **Test plan before the test.** Writing the measurement rules and pass criteria first kept the Phase 7 report honest.
   For example, RTO ends at *independent* verification, not at the host's own claim.

## Surprises and how they were handled

| What happened | Lesson |
|---|---|
| Windows hit its **commit-memory limit** (24 GB) several times: Docker hung on container start, Node crashed ("Zone Allocation failed"), browsers crashed in tests | Check memory before blaming code. Use `--workers=1` or `2` for Playwright. `docker desktop restart` fixes a wedged engine |
| A Playwright test passed locally but **failed on GitHub's Linux runners** (a page-transition race) | GitHub logs need admin rights. Reproducing in the official Playwright Linux image (`mcr.microsoft.com/playwright:v1.64.1-noble`) found it in minutes |
| The Resource Groups **Tagging API kept listing deleted** instances, volumes and endpoints | Confirm cleanup with `describe-*` calls, not tag searches |
| The **IAM policy simulator** reported `explicitDeny` for allowed actions | The region guardrail needs `aws:RequestedRegion` in the simulation context |
| Git Bash **rewrote `/aws/...` paths** into Windows paths | `MSYS_NO_PATHCONV=1` |
| The Identity Center policy editor added an **empty `Statement1`** that broke the paste | Replace the editor's whole contents, never append |
| Claude Code's **auto-mode safety check** blocked IaC applies that the plan had not explicitly covered, and a lasting "no approvals" memory rule | Expected behaviour. Applies ran once the owner allowed `terraform apply` in `/permissions`; approvals were kept explicit per step |
| **Port 4174** was taken by another local project | `E2E_PORT` makes the e2e port configurable |
| `docker compose run` from a non-interactive shell **hung without `-T`** | Always pass `-T` in scripts |

## Measured results (single runs)

| Drill | RTO | RPO | Notes |
|---|---|---|---|
| Phase 6 controlled drill | 7 min 15 s (host-reported) | 19 min 38 s | Included 2 min 9 s of human approval time |
| Phase 7 disaster drill | **5 min 29 s** (independent) | **26 s** | Primary stopped; fresh-clone workstation; 10/10 criteria |

About 3.5 minutes of every recovery is **host setup**: installing Docker (≈ 105 s), pulling PostgreSQL (≈ 50 s) and
building the CMS image (≈ 52 s). The database restore itself took under 1 second for this dataset.

## Open items, in priority order

1. **Unattended off-site upload (most important).** Today the scheduler verifies hourly but uploads only when an
   operator runs `upload --all`. Until that is automated, the *real* RPO depends on the operator and can exceed the
   60-minute target.
   - Recommended: **IAM Roles Anywhere** (an X.509 certificate on the office server → short-lived role credentials
     for `bdr-recovery-backup-writer`), then `upload` after every verified backup in the scheduler.
   - Alternative: a scheduled task on an always-on workstation using SSO (fragile: the session expires).
2. **Auto-teardown on drill failure.** If a drill fails after provisioning, have the runner prepare the teardown plan
   immediately, so the operator only has to approve.
3. **Faster recovery host.**
   - Publish the CMS image to GitHub Container Registry from CI and pull it instead of building (−50 s).
   - Pre-pull or bake an AMI with Docker and PostgreSQL (−2.5 min).
   - Expected RTO ≈ 2 min.
4. **Automate the independent check** (SSM port forward plus API queries) inside the runner, so the report's RTO end
   is always independent.
5. **Record RPO against the disaster time.** Let the operator enter T_disaster when declaring, so the runner reports
   RPO by the blueprint's definition.
6. **Dependabot pull requests.** Several early PRs failed CI because of the e2e race that is now fixed. Re-run or
   rebase them and merge the safe ones. Watch the Node 20 deprecation for `actions/checkout` and `actions/setup-node`
   (the actions-update PR covers it).
7. **Repeat the drill** with a larger synthetic dataset and at a realistic RPO point (a backup ~50 minutes old), so
   the numbers stop resting on single runs.
8. **Security hardening when real data arrives:** SSE-KMS, S3 Object Lock or signed manifests, S3 access logging
   (ADR-012 revisit list).
