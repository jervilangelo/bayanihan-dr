# Phase 7 test plan: disaster drill

Written **before** the drill (2026-11-05). The results go in `phase7-disaster-drill.md`, judged against this
plan without changing it afterwards.

## Scenario

A typhoon cuts power to the Naga City office. The primary CMS (its database and API) stops. A trusted operator
on another workstation recovers the CMS into AWS using only what lives outside the office: the GitHub repository,
the off-site backups in S3, the Terraform state in S3, and their own SSO sign-in.

## Procedure

1. **Known records.** Create marker farmer **A** (`BFC-99001`) on the primary. Back up, verify and upload off-site.
   Then create marker farmer **B** (`BFC-99002`) *after* that backup.
2. **Disaster.** Stop the primary CMS containers (`db`, `api`, backup scheduler). Record **T_disaster** and
   confirm the CMS is unreachable.
3. **Alternate workstation.** Fresh `git clone` of the public repository into an empty folder. Copy in only
   `backend.hcl` and `recovery.tfvars` (the operator's two local settings files). New Python virtual environment.
   Start the job runner from that clone. Nothing comes from the original working copy or the stopped primary.
4. **Declare and recover.** Create a drill job from the newest off-site recovery point (**T_declared**, the RTO
   start). Approve the guarded plan, then follow the host's progress.
5. **Independent verification** from the workstation through an SSM port forward to the recovery host's CMS:
   `/health/ready`, record totals, marker A present, marker B absent. Record **T_verified**.
6. **Corrupted backup test.**
   - Upload a corrupted copy of the archive of an *older* recovery point as a new S3 object version.
   - Run a second drill from that point. It must **fail closed** at checksum verification without starting a CMS.
   - Restore the good object version, then tear down.
7. **Teardown and cleanup.** Remove the drill environment and check in AWS that nothing remains. Restart the
   primary CMS and remove the markers.
8. **Cost.** Instance runtime × verified prices, plus Cost Explorer month-to-date before and after (billing lags
   by up to 24 h).

## Measurement boundaries

| Measure | Start | End |
|---|---|---|
| **RTO** (blueprint §5) | T_declared: drill job created | T_verified: independent check passes from the workstation. The host's own `recovery-complete` time is reported as well. |
| **RPO** (blueprint §5) | Time of the restored backup (`scheduled_at`) | T_disaster |
| Provisioning | `terraform apply` start | apply finished |
| Database restore | `pg_restore` start | finished (host-measured, ms) |
| Application start | CMS container build/start | `/health/ready` OK |
| Detection gap | T_disaster | T_declared. Reported, but not part of the RTO by the blueprint's definition. |

Clocks: the workstation uses Windows time sync and the host uses Amazon Time Sync. Differences of about a second
are expected and are noted rather than corrected.

## Pass criteria

| # | Criterion |
|---|---|
| P1 | Recovery runs from the fresh clone with the primary stopped |
| P2 | The drill job succeeds; the plan guard allows only the drill footprint |
| P3 | Restored record counts equal the backup manifest |
| P4 | Marker A is present in the recovered CMS (independent check) |
| P5 | Marker B is absent: data written after the backup is lost, as the RPO predicts |
| P6 | RTO ≤ 30 min |
| P7 | RPO ≤ 60 min |
| P8 | A corrupted off-site backup is refused (job fails at `verify-checksum`, no CMS started) |
| P9 | After teardown: 0 project instances, VPCs, network interfaces, volumes and Elastic IPs; standby plan has no changes |
| P10 | Drill cost stays inside the PHP 300–500 budget |

Any criterion that fails is reported as a failure, with its cause, and is not retried until it passes.
