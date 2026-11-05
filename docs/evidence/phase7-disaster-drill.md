# Phase 7 report: disaster drill

- **Date:** 2026-11-05, times in UTC
- **Plan:** [`phase7-test-plan.md`](phase7-test-plan.md), written before the drill and not changed afterwards
- **Region:** ap-southeast-1. Account IDs are left out on purpose.

## Verdict: PASS, 10 of 10 criteria, with the limitations below

The primary CMS was stopped. From a fresh clone of the public repository, with only the operator's two local
settings files, the CMS was recovered in AWS from an off-site backup. It was then **verified independently from
the workstation 5 min 29 s after the incident was declared**. Data written after the last backup was lost, as the
RPO predicts. A deliberately corrupted off-site backup was refused before any data was restored. Afterwards
nothing was left running, and the primary was brought back.

This is one controlled drill. Its RPO is far better than the design target only because a backup ran 26 seconds
before the disaster. See the limitations.

## Timeline

| Time | Event |
|---|---|
| 06:30:16.020 | Backup `20261105T063016Z` starts (contains marker A `BFC-99001`); verified, then uploaded off-site |
| ~06:30:35 | Marker B `BFC-99002` written to the primary, **after** the backup |
| **06:30:42.097** | **T_disaster**: primary `db`, `api` and backup scheduler stopped; `/health/ready` unreachable |
| 06:31–06:32 | Alternate workstation: fresh `git clone` (commit `1be8f2a`), `backend.hcl` and `recovery.tfvars` copied in, new virtual environment, `terraform init` against S3 state, runner started |
| **06:32:16.901** | **T_declared**: drill job `job-20261105T063216Z-399fc1` created (RTO start) |
| 06:32:44.880 | Plan guard passes: 11 to add, 0 to change, 0 to destroy |
| 06:32:45.764 | Approved |
| 06:32:45.785 → 06:33:15.470 | `terraform apply` (29.7 s) |
| 06:33:16 → 06:35:00 | Host installs Docker and Git (104.6 s) |
| 06:35:03 → 06:35:22 | CMS source fetched at the pinned SHA, backup downloaded (96,738 bytes), SHA-256 matches the manifest |
| 06:35:24 → 06:36:16 | PostgreSQL 16 started (52.1 s, including the image pull) |
| 06:36:19 → 06:36:23 | Database restored (`pg_restore` 955 ms) |
| 06:36:26 → 06:37:18 | CMS image built and started (51.9 s); `/health/ready` OK at 06:37:30.552 |
| 06:37:33.224 | Host reports `recovery-complete` (counts match the manifest) |
| **06:37:45.836** | **T_verified**: independent check from the workstation through an SSM port forward passes |
| 06:38:03 → 06:39:08 | Teardown job: 11 to destroy, approved, done |

## Measurements (definitions from the test plan)

| Measure | Result | Target |
|---|---|---|
| **RTO** (T_declared → T_verified, independent) | **328.9 s (5 min 29 s)** | ≤ 30 min |
| RTO, host-reported (T_declared → `recovery-complete`) | 316.3 s | n/a |
| **RPO** (T_disaster − backup time) | **26.1 s** | ≤ 60 min |
| Detection gap (T_disaster → T_declared) | 94.8 s, mostly setting up the alternate workstation; not part of RTO | n/a |
| Approval wait | 28.9 s | n/a |
| Provisioning (`terraform apply`) | 29.7 s | n/a |
| Database restore (`pg_restore`) | 0.955 s | n/a |
| Application start (container build/start → ready) | 51.9 s build/start, ready about 12 s later | n/a |
| Backup age at recovery | 26.1 s at the disaster; 2 min 1 s at declaration | n/a |
| Recovery success | Yes, independently verified | n/a |

## Pass criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| P1 | Recovery runs from the fresh clone with the primary stopped | **PASS** | Clone had no `backups/`, no runner state and no local Terraform state; primary `/health/ready` unreachable throughout |
| P2 | Drill succeeds; the guard allows only the drill footprint | **PASS** | Job succeeded; plan 11 create / 0 / 0 |
| P3 | Restored counts equal the manifest | **PASS** | farmers 1051, inventory 26, transactions 3001, from both the host and the independent check |
| P4 | Marker A present | **PASS** | Independent API query found `BFC-99001` |
| P5 | Marker B absent | **PASS** | Independent API query found no `BFC-99002` |
| P6 | RTO ≤ 30 min | **PASS** | 5 min 29 s |
| P7 | RPO ≤ 60 min | **PASS** | 26.1 s, with the caveat in the limitations |
| P8 | Corrupted off-site backup refused | **PASS** | Job `job-20261105T064008Z-5da0cf` failed at `verify-checksum` (manifest `19eef4e7…`, download `8fd33b26…`); start-db, restore and start-app never ran |
| P9 | Nothing left after teardown | **PASS** | 0 instances, VPCs, network interfaces, volumes and Elastic IPs; standby plan has no changes |
| P10 | Cost inside the budget | **PASS** | About USD 0.007 for Phase 7 (below) |

### Corrupted-backup test (P8) in detail

1. The current S3 object `backups/20261104T081749Z/cms.dump` (the good version) was replaced by a copy with one
   byte flipped, uploaded as a new object version by the operator role.
2. A drill was run from that point. Preflight passed: the manifest was still verified, as intended, because the
   test is whether the host catches it. The plan passed the guard, it was approved, and the host provisioned and
   downloaded the copy.
3. The host refused it at `verify-checksum` and reported both hashes. The job failed with nothing restored.
4. A teardown job removed the host (11 deleted, done at 06:45:46).
5. The corrupted object version was deleted. The good version (`Z4tk…`) is current again and its SHA-256 matches
   the manifest.

## Cost

| Run | Host lifetime | Cost at USD 0.0342/h |
|---|---|---|
| Disaster drill | 06:32:45 → 06:39:06 (6 min 21 s) | about USD 0.0036 |
| Corrupted-backup drill | 06:40:33 → 06:45:44 (5 min 11 s) | about USD 0.0030 |
| **Phase 7 total** | 11 min 32 s | **about USD 0.007 (about PHP 0.40)** |

Cost Explorer month-to-date for the whole account: USD 0.1269 before Phase 7 and USD 0.1312 after. Billing lags
by up to 24 hours, so today's drills may not be fully included yet. Re-check in Phase 10.

## Limitations (stated plainly)

1. **The measured RPO is not the typical RPO.** A backup ran 26 s before the disaster. With the hourly schedule, the
   worst case is close to 60 minutes plus backup, verify and upload time. That is still inside the target, but
   only just.
2. **Off-site copies are made by hand.** The hourly scheduler verifies locally but does not upload unattended
   (ADR-013). If the operator does not run `upload --all`, the newest *off-site* point can be much older than the
   newest local backup, and **the real RPO would miss the 60-minute target**. Unattended upload, for example with
   IAM Roles Anywhere, is the most important open item.
3. **A failed drill leaves its host running** until a teardown job is run. The runner's error message says so, and
   here the teardown followed 16 s later. An automatic teardown on failure would remove this risk.
4. **About 3.5 min of the RTO is host setup:** installing Docker (105 s), pulling PostgreSQL (about 50 s) and
   building the CMS image (52 s). A prebuilt AMI and a published CMS image (Phase 8) would cut it to about 1 min.
5. **Clocks:** the workstation uses Windows time and the host uses Amazon Time Sync. The host-reported and
   independent end times differ by 12.6 s, which is within the expected margin.
6. **One run.** These numbers come from a single drill with a small synthetic dataset (about 97 KB). A larger
   database would mainly lengthen download and restore.
7. **The runner reports RPO to the declaration time** (120.9 s here), not to the disaster time, because the runner
   cannot know when the disaster happened. This report uses the test plan's definition.

## Cleanup

- Primary CMS restarted (`/health/ready` OK). Both markers deleted; 1,050 farmers again.
- AWS is back to the standby footprint; `terraform plan` shows no changes.
- The alternate-workstation clone stayed in the session scratch folder and was not committed.

## Audit trail (alternate-workstation runner)

```
06:32:16.902 job-created    063216Z-399fc1 recovery-drill from 20261105T063016Z
06:32:44.894 plan-ready     063216Z-399fc1 {'create': 11, 'update': 0, 'delete': 0, 'replace': 0}; est. USD 0.0342/h
06:32:45.769 job-approved   063216Z-399fc1
06:37:43.351 job-succeeded  063216Z-399fc1 recovery verified
06:38:03.210 job-created    063803Z-aa9657 teardown
06:38:24.735 plan-ready     063803Z-aa9657 {'create': 0, 'update': 0, 'delete': 11, 'replace': 0}
06:38:25.702 job-approved   063803Z-aa9657
06:39:08.590 job-succeeded  063803Z-aa9657 teardown complete
06:40:08.180 job-created    064008Z-5da0cf recovery-drill from 20261104T081749Z
06:40:33.306 plan-ready     064008Z-5da0cf {'create': 11, ...}
06:40:33.910 job-approved   064008Z-5da0cf
06:44:15.506 job-failed     064008Z-5da0cf host step verify-checksum failed: SHA-256 mismatch
06:44:31.774 job-created    064431Z-ffb13a teardown
06:45:00.598 plan-ready     064431Z-ffb13a {'create': 0, 'update': 0, 'delete': 11, 'replace': 0}
06:45:00.880 job-approved   064431Z-ffb13a
06:45:46.453 job-succeeded  064431Z-ffb13a teardown complete
```
