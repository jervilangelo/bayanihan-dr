# Phase 5 deployment record

- **Date:** 2026-11-05
- **Region:** ap-southeast-1
- **Applied by:** the operator SSO role `BayanihanDR-Developer-V5`, which has `ReadOnlyAccess` plus the project-scoped
  inline policy in `docs/aws/bayanihandr-developer-inline-policy.json`
- **Approvals:** the project owner approved the state bucket and the standby setup on 2026-11-05, with SSE-S3
  (ADR-012) and AWS Budgets alerts to the owner's email.

Account IDs are left out on purpose (blueprint §11.4).

## Pre-apply checks

- **Pricing** (AWS Pricing API, on-demand, ap-southeast-1):
  - t3.small: USD 0.0264/h
  - public IPv4: USD 0.005/h
  - gp3: USD 0.096/GB-month
  - S3 Standard: USD 0.025/GB-month
  - CloudWatch alarm: USD 0.10/month
- **Guardrails,** confirmed with the IAM policy simulator (region context ap-southeast-1):
  - allowed: `bayanihandr-*` buckets, `bdr-*` roles and budgets;
  - denied: other buckets, other regions, IAM users, NAT gateways and RDS.

## Applied

| Step | Plan | Result |
|---|---|---|
| `terraform/bootstrap` (state bucket) | 7 to add | 7 added. State then migrated into the bucket itself (`bootstrap/terraform.tfstate`); a follow-up plan shows no changes. |
| `terraform/environments/recovery`, standby + budget | 13 to add | 13 added, 0 changed, 0 destroyed. State in `recovery/terraform.tfstate` with S3 native locking. |

## Resource inventory (verified directly with the AWS CLI after apply)

| Resource | Verified settings |
|---|---|
| S3 `bayanihandr-tfstate-<account>-ap-southeast-1` | AES256, versioning on, all 4 public-access blocks, not public, TLS-only policy, ACLs disabled, `prevent_destroy` |
| S3 `bayanihandr-backups-<account>-ap-southeast-1` | Same settings, plus lifecycle (30 days current, 7 days noncurrent, abort multipart after 1 day) and `force_destroy = false` |
| IAM role and instance profile `bdr-recovery-recovery-host` | EC2 trust; `AmazonSSMManagedInstanceCore`; inline read-backups/write-logs policy; 1 h sessions |
| CloudWatch log group `/bayanihandr/recovery/recovery` | 7-day retention |
| AWS Budgets `bdr-recovery-monthly-cost` | USD 10/month; email at 50% actual, 100% actual and 100% forecast |
| IAM role `bdr-recovery-backup-writer` | Trust: only the operator SSO role. Policy: `s3:PutObject` on `backups/*`. Checked: listing, deleting and writing outside `backups/` all return AccessDenied. |
| EC2 instances / VPCs / Elastic IPs | **0 / 0 / 0**: no paid compute in standby |

**Expected standby cost:** S3 storage and requests for small synthetic backups, well under USD 0.10/month.
The writer role was applied separately (2 added) after its own approval.

## Off-site upload and read-back

Uploaded with `python -m bdr_engine upload --all`, using 1-hour credentials for the writer role passed through the
environment. Only verified backups are sent; the failed backup `20261104T081808Z` was skipped.

| Backup | S3 | Read-back check |
|---|---|---|
| `20261105T055524Z` | AES256, versioned, S3-stored SHA-256 matches the one sent | Downloaded 96,669 bytes. SHA-256 matches the local manifest and the S3 manifest. `pg_restore --list` reads it (4 tables of data). Records: farmers 1050, inventory 26, transactions 3001. |
| `20261104T081749Z` | AES256, versioned, checksum matches | Same checks pass. |

The downloaded copies were deleted after the check.

## Known limitation

The hourly scheduler does not upload automatically yet. Unattended uploads need credentials that last longer than an
SSO session, for example IAM Roles Anywhere. That is decided in Phase 6. Until then, off-site copies are made with
`upload --all` from an operator session.
