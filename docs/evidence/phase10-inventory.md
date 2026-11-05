# Phase 10: AWS inventory, destroy-plan review and residual billing

- **Date:** 2026-11-05, about 07:40 UTC (15:40 PHT)
- **Identity:** SSO role `BayanihanDR-Developer-V5`
- **Region:** ap-southeast-1. Account IDs are left out.
- **Decision:** the owner keeps the **standby** environment running after the project (2026-11-05). The full destroy
  was **reviewed but not applied**. The procedure is in RUNBOOK §11.

## Current inventory (verified with `describe-*` calls)

| Resource | Status |
|---|---|
| S3 `bayanihandr-backups-<account>-ap-southeast-1` | Present. SSE-S3, versioned, private, TLS-only, lifecycle 30/7 days. Off-site recovery points: `20261104T081749Z`, `20261105T055524Z`, `20261105T060000Z`, `20261105T063016Z` |
| S3 `bayanihandr-tfstate-<account>-ap-southeast-1` | Present. `recovery/terraform.tfstate`, `bootstrap/terraform.tfstate` |
| IAM roles | `bdr-recovery-recovery-host` (+ instance profile), `bdr-recovery-backup-writer` |
| CloudWatch log group | `/bayanihandr/recovery/recovery` (7-day retention) |
| AWS Budgets | `bdr-recovery-monthly-cost`, USD 10/month |
| EC2 instances (project) | 0 running. 2 drill hosts still listed as `terminated` (AWS removes terminated instances from listings on its own; the third had already gone) |
| VPCs, subnets, security groups, VPC endpoints, EBS volumes, Elastic IPs (project) | **0**. Each ID that the Tagging API still listed returned `NotFound` from `describe-*` |
| `terraform plan` of the standby configuration | No changes (exit code 0) |

The Resource Groups Tagging API still returned ARNs for deleted drill resources (3 instances, 3 volumes, 3 security
groups, 3 VPC endpoints, 3 security-group rules). This is AWS's eventual cleanup of that index. Direct `describe-*`
calls confirmed every one of them is gone.

## Destroy plan (reviewed, not applied)

`terraform plan -destroy -var-file=recovery.tfvars` in `terraform/environments/recovery`:

```
Plan: 0 to add, 0 to change, 15 to destroy.
  module.identity.aws_iam_instance_profile.recovery_host
  module.identity.aws_iam_role.backup_writer[0]
  module.identity.aws_iam_role.recovery_host
  module.identity.aws_iam_role_policy.backup_writer[0]
  module.identity.aws_iam_role_policy.recovery_host
  module.identity.aws_iam_role_policy_attachment.recovery_host_ssm
  module.monitoring.aws_budgets_budget.monthly[0]
  module.monitoring.aws_cloudwatch_log_group.recovery
  module.storage.aws_s3_bucket.backups
  module.storage.aws_s3_bucket_lifecycle_configuration.backups
  module.storage.aws_s3_bucket_ownership_controls.backups
  module.storage.aws_s3_bucket_policy.backups
  module.storage.aws_s3_bucket_public_access_block.backups
  module.storage.aws_s3_bucket_server_side_encryption_configuration.backups
  module.storage.aws_s3_bucket_versioning.backups
```

Review notes:
- Exactly the standby footprint, nothing else.
- `aws_s3_bucket.backups` has `force_destroy = false`. The apply would **fail** until every object version is
  deleted. That is intentional: emptying the backups is a separate, deliberate step (RUNBOOK §11.2).
- The state bucket is in a separate configuration (`terraform/bootstrap`) with `prevent_destroy`, so it is not part
  of this plan.

## Residual billing check

Cost Explorer, account month-to-date for 2026-11-01 to 2026-11-06:
- S3 USD 0.00109 and CloudWatch USD 0.00004 (this project).
- Amplify, AppSync and DynamoDB (another project).
- Tax USD 0.01.
- **EC2 and VPC charges for the 2026-11-05 drills are not yet visible** (billing lag). They are expected to total
  ≈ USD 0.01. See [COST.md](../COST.md) for the command to re-check after 2026-11-06.

## Evidence preserved in the repository

| Phase | File |
|---|---|
| 4 | [phase4-plan-review.md](phase4-plan-review.md) |
| 5 | [phase5-deployment.md](phase5-deployment.md) |
| 6 | [phase6-recovery-drill.md](phase6-recovery-drill.md) |
| 7 | [phase7-test-plan.md](phase7-test-plan.md), [phase7-disaster-drill.md](phase7-disaster-drill.md) |
| 9 | Live-site test suite `frontend/e2e-public/`; published data `frontend/src/data/recorded-drills.ts` |
| 10 | this file; screenshots in [../screenshots/](../screenshots/) |

The raw job records and audit logs stay on the operator workstation (`backend/var/jobs/`, git-ignored). Their
relevant contents are reproduced in the Phase 6 and Phase 7 evidence files.
