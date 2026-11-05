# Phase 6 evidence: first controlled recovery drill

- **Date:** 2026-11-05, times in UTC
- **Runner:** `bdr_runner` 0.1.0 on the operator workstation, signed in with the `BayanihanDR-Developer-V5` SSO role
- **Approvals:** the project owner approved the drill (job `job-20261105T061502Z-cccefc`) and the teardown that
  followed it.
- **Region:** ap-southeast-1. Account IDs are left out on purpose.

**Result: the CMS was recovered in AWS from an off-site backup and verified. RTO 7.2 min (target 30), RPO 19.6 min
(target 60).** This is one measured drill, not a guarantee. Phase 7 repeats it as a full disaster exercise with the
primary stopped.

## Drill job `job-20261105T061502Z-cccefc`

- **Recovery point:** `20261105T055524Z` (verified, stored off-site, SHA-256 checked again on download)
- **CMS source:** commit `f1f86cb` (pinned by SHA)

| Step | Start → finish | Detail |
|---|---|---|
| Preflight | 06:15:03 → 06:15:09 | SSO role OK; the point is verified off-site; no host running; CMS commit pinned |
| Plan + guard | 06:15:09 → 06:15:37 | 11 to add, 0 to change, 0 to destroy, matching the drill footprint; estimate USD 0.034/h |
| Approval | 06:15:37 → 06:17:45 | Approved by typing the job ID |
| Provision (`terraform apply` of the saved plan) | 06:17:45 → 06:18:17 | VPC, subnet, IGW, route table, S3 endpoint, 2 security groups, t3.small host, alarm |
| Install Docker and Git | 06:18:17 → 06:19:44 | Docker 25.0.14 |
| Fetch CMS source | 06:19:47 → 06:19:52 | commit f1f86cb |
| Download backup | 06:19:55 → 06:20:03 | 96,669 bytes from S3 through the gateway endpoint |
| Verify checksum | 06:20:06 | SHA-256 matches the verified manifest |
| Start PostgreSQL 16 | 06:20:08 → 06:21:01 | |
| Restore | 06:21:03 → 06:21:07 | `pg_restore` itself took 913 ms |
| Start CMS | 06:21:10 → 06:22:02 | image built from source on the host |
| Health | 06:22:15 | `/health/ready` OK |
| Verify records | 06:22:16 | farmers 1050/1050, inventory 26/26, transactions 3001/3001; the API serves data |
| Report | 06:22:18 | |

| Measure | Value | How it is measured |
|---|---|---|
| **RTO** | **434.9 s (7.2 min)**, within the 30 min target | From job creation (incident declared, 06:15:02.999) to the host's `recovery-complete` event (06:22:17.915) |
| **RPO** | **1178.3 s (19.6 min)**, within the 60 min target | Declared time minus the backup time (05:55:24) |
| Approval wait | 162.6 s | Counted inside the RTO, as in a real incident |
| Provisioning | 31.9 s | `terraform apply` |
| Host restore, install to verified | 239.0 s | Host clock (Amazon Time Sync) against the workstation clock |

## Audit trail (`backend/var/jobs/audit.jsonl`)

```
06:15:03 job-created    recovery-drill from 20261105T055524Z
06:15:37 plan-ready     {'create': 11, 'update': 0, 'delete': 0, 'replace': 0}; est. USD 0.034/h
06:17:45 job-approved   plan: {'create': 11, ...}
06:22:18 job-succeeded  recovery verified
06:22:46 job-created    teardown
06:23:12 plan-ready     {'create': 0, 'update': 0, 'delete': 11, 'replace': 0}
06:23:20 job-approved
06:23:55 job-succeeded  teardown complete
```

## Teardown job `job-20261105T062246Z-d71b61`

- **Plan:** 11 to destroy, exactly the drill footprint. The guard would have refused anything touching backups,
  IAM or the budget.
- **Duration:** destroy 06:23:20 → 06:23:53, then confirmation that no hosts remain.
- **Checked directly with the AWS CLI afterwards:**
  - the instance is `terminated`;
  - 0 VPCs, 0 network interfaces, 0 volumes, 0 Elastic IPs tagged for the project;
  - both off-site recovery points are still in S3;
  - `terraform plan` of the standby configuration shows **no changes**.

## Cost

The host ran about 6 minutes (06:17:45 → 06:23:53). At USD 0.034/h, the drill cost about **USD 0.004**.

## Limitations seen

- The CMS image is built on the host (52 s) and Docker is installed at boot (87 s), about 2.3 minutes of the RTO.
  A prebuilt image (Phase 8 CI) and a baked AMI would shorten this.
- Verification is reported by the host itself. Independent checks from the workstation (SSM port forwarding)
  are planned for the Phase 7 drill.
- Off-site uploads are still made from an operator session; the hourly scheduler does not upload unattended (ADR-013).
