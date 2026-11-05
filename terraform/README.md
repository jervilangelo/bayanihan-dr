# BayanihanDR Terraform

This folder holds the AWS infrastructure that BayanihanDR recovers into (blueprint §8). The region is `ap-southeast-1`
(Singapore).

> **Phase 4 status:** the code is written, formatted, validated, linted, scanned and tested on a mocked provider.
> **Current state (Phase 10):** the standby setup stays deployed (ADR-016); no drill environment is running. Reviewed
> destroy plan: [docs/evidence/phase10-inventory.md](../docs/evidence/phase10-inventory.md).
> **Phase 5:** the state bucket and the standby setup are applied (see [docs/evidence/phase5-deployment.md](../docs/evidence/phase5-deployment.md)).
> Real read-only plans have been reviewed: 12 resources in standby, 24 in a drill (see
> [docs/evidence/phase4-plan-review.md](../docs/evidence/phase4-plan-review.md)). **Nothing has been applied.**
> `apply` happens only in Phase 5, after explicit approval.

## Layout

```text
terraform/
├── bootstrap/                 # remote-state bucket; applied once, reviewed separately (Phase 5)
├── environments/recovery/     # the root configuration you plan and apply
│   ├── tests/                 # terraform test, mocked AWS provider (no credentials)
│   ├── backend.example.hcl    # copy to backend.hcl (git-ignored)
│   └── recovery.example.tfvars
└── modules/
    ├── networking/            # VPC, one public subnet, IGW, S3 gateway endpoint, no-inbound security group
    ├── compute/               # temporary EC2 recovery host + bootstrap script
    ├── storage/               # encrypted, versioned, private backup bucket with lifecycle
    ├── identity/              # instance role (SSM, read backups), optional upload-only backup-writer role
    └── monitoring/            # log group, host status alarm, optional AWS Budgets alert
```

## Two lifecycles, one switch

| `recovery_enabled` | What exists | Idle cost |
|---|---|---|
| `false` (default) | Backup bucket, IAM roles, log group, optional budget | S3 storage only, a few cents a month for small backups |
| `true` (approved drill) | Everything above, plus the VPC, subnet, IGW, S3 endpoint, security group, EC2 host and status alarm | Paid while running; see below |

Setting `recovery_enabled` back to `false` and applying removes the compute and network. Backups are not touched.

## Planned resources

**Standby** (`recovery_enabled = false`):
- **storage:** `aws_s3_bucket` plus its public access block, ownership controls, versioning, SSE-S3 encryption,
  lifecycle (30 days current, 7 days noncurrent) and a TLS-only policy.
- **identity:** `aws_iam_role` and `aws_iam_instance_profile` for the recovery host, with
  `AmazonSSMManagedInstanceCore` and an inline read-backups/write-logs policy. Optional: an upload-only backup-writer role.
- **monitoring:** `aws_cloudwatch_log_group` with 7-day retention. Optional: an `aws_budgets_budget` with alerts at
  50%, 100% and forecast 100%.

**Drill** adds:
- **networking:** `aws_vpc` (10.42.0.0/16), `aws_subnet` (10.42.1.0/24), `aws_internet_gateway`, a route table and
  association, an `aws_vpc_endpoint` (S3 gateway, free), a locked default security group, and a security group
  with no inbound rules and outbound TCP 443 only.
- **compute:** an `aws_instance` (t3.small, Amazon Linux 2023), with IMDSv2 only, a 20 GiB encrypted gp3 root
  volume, standard CPU credits, a public IP for outbound traffic, and termination on shutdown.
- **monitoring:** an `aws_cloudwatch_metric_alarm` on the host's status check.

Not used at all: NAT Gateway, RDS, load balancers, EKS, Elastic IPs, SSH key pairs, IAM users and access keys.

## Drill cost (prices verified 2026-11-05)

Prices are on-demand list prices for ap-southeast-1 from the AWS Pricing API, checked on 2026-11-05.

| Item | Price | 4-hour drill |
|---|---|---|
| EC2 t3.small | USD 0.0264/h | USD 0.11 |
| Public IPv4 address | USD 0.005/h | USD 0.02 |
| EBS gp3 20 GiB | USD 0.096/GB-month | under USD 0.01 |
| CloudWatch status alarm | USD 0.10/alarm-month (prorated) | under USD 0.01 |
| S3 Standard | USD 0.025/GB-month | cents |

A drill costs about USD 0.15 (around PHP 9). Standby costs well under USD 0.10 a month for small synthetic backups.
Both are far inside the PHP 300–500 planning budget. Most of the risk comes from forgetting to switch a drill off;
the budget alert and the `terminate` shutdown behaviour help with that.

## Checks run in Phase 4

```bash
terraform fmt -recursive -check                                   # formatting
terraform -chdir=environments/recovery init -backend=false && terraform -chdir=environments/recovery validate
terraform -chdir=bootstrap init -backend=false && terraform -chdir=bootstrap validate
terraform -chdir=environments/recovery test                       # 15 tests, mocked provider
docker run --rm -v "$PWD:/data" -w /data --entrypoint sh ghcr.io/terraform-linters/tflint \
  -c 'tflint --init && tflint --chdir=environments/recovery --config=/data/.tflint.hcl'
docker run --rm -v "$PWD:/src:ro" aquasec/trivy config /src     # security scan
```

Trivy findings that are accepted on purpose are annotated in the code (`#trivy:ignore`) and explained in ADR-012.

## Real plan (once a dedicated AWS profile exists)

```bash
aws sso login --profile <bayanihandr-profile>
export AWS_PROFILE=<bayanihandr-profile>
cd terraform/environments/recovery
terraform init -backend=false        # local state for review only, until the state bucket exists
terraform plan -var-file=recovery.tfvars -out=review.tfplan    # *.tfplan is git-ignored
terraform plan -var-file=recovery.tfvars -var recovery_enabled=true    # review the drill footprint too
```

The profile needs read access only for `plan` (EC2, IAM, S3, CloudWatch, Budgets, SSM `GetParameter`, STS).

## State and bootstrap (Phase 5)

1. Apply `bootstrap/` with local state. This creates `bayanihandr-tfstate-<account>-ap-southeast-1`, which is
   versioned, encrypted, private, TLS-only and has `prevent_destroy`.
2. Copy `environments/recovery/backend.example.hcl` to `backend.hcl` and run `terraform init -backend-config=backend.hcl`.
   Locking uses S3 lockfiles (`use_lockfile`), so no DynamoDB table is needed.
3. The state lives in AWS, so it survives the loss of the office. An operator on any trusted laptop with SSO access
   can plan and recover.
