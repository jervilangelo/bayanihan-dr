# Phase 4 plan review: `terraform/environments/recovery`

- **Date:** 2026-11-05
- **Tools:** Terraform 1.16.6, AWS provider 6.72.0
- **Identity:** IAM Identity Center permission set `BayanihanDR-Developer-V5` (AWS managed `ReadOnlyAccess`, 4 h sessions)
- **Region:** ap-southeast-1
- **State:** local, review only (a git-ignored `backend_override.tf`); the remote-state bucket is a Phase 5 bootstrap
- **Result:** both plans are valid. **Nothing was applied**, and afterwards no BayanihanDR bucket or VPC exists in the account.

Account IDs are left out of this record on purpose (blueprint §11.4).

## Standby (defaults, `recovery_enabled = false`)

`Plan: 12 to add, 0 to change, 0 to destroy.`

| Module | Resources |
|---|---|
| storage | S3 bucket `bayanihandr-backups-<account>-ap-southeast-1`, with public access block, ownership controls, versioning, SSE-S3 encryption, lifecycle and a TLS-only policy |
| identity | recovery-host role, inline policy, SSM managed-policy attachment, instance profile |
| monitoring | log group `/bayanihandr/recovery/recovery`, kept 7 days |

## Drill (`recovery_enabled = true`, budget email set)

`Plan: 24 to add, 0 to change, 0 to destroy.` That is the standby set plus the following:

| Module | Resources and the values checked |
|---|---|
| networking | VPC `10.42.0.0/16`, subnet `10.42.1.0/24` in `ap-southeast-1a`, IGW, route table (`0.0.0.0/0` → IGW) and association, S3 gateway endpoint `com.amazonaws.ap-southeast-1.s3`, default security group with no rules, host security group whose only rule is egress TCP 443 |
| compute | `t3.small`; AMI `ami-01127915c7b29e7ca` (al2023-ami-2023.12.20261102.0-kernel-6.18-x86_64, owner alias `amazon`, matching the public SSM parameter); `http_tokens = required`; `cpu_credits = standard`; 20 GiB gp3 root volume, encrypted; `instance_initiated_shutdown_behavior = terminate`; public IPv4 for outbound traffic |
| monitoring | EC2 status-check alarm; AWS Budgets monthly budget of USD 10.00 |

## Checks outside the plan

- `t3.small` is offered in ap-southeast-1a, 1b and 1c (`describe-instance-type-offerings`).
- No NAT Gateway, Elastic IP, load balancer, RDS, key pair, IAM user or access key appears in either plan.

## Open before any apply (Phase 5)

- Verify current ap-southeast-1 pricing (OD-6). The figures in `terraform/README.md` are approximate.
- Confirm ADR-012 (SSE-S3, no access logging).
- `ReadOnlyAccess` cannot apply. Phase 5 needs a separately scoped permission set for creating resources.
- Bootstrap the state bucket, then switch to the S3 backend.
