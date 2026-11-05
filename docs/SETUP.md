# Rebuild BayanihanDR from scratch

Everything needed to reproduce the project on a new machine and a new AWS account, in the order it was built.
For day-to-day operation see [RUNBOOK.md](RUNBOOK.md). For how it fits together see [ARCHITECTURE.md](ARCHITECTURE.md).

## 0. Prerequisites

| Tool | Version used | Notes |
|---|---|---|
| Git | any recent | Git Bash on Windows is assumed in commands |
| Docker Desktop | 4.98 (Engine 29) | Runs the CMS, the backup engine and the test databases |
| Node.js | 22+ (24 used locally) | Dashboard |
| Python | 3.12+ (3.14 used locally) | Job runner. The engine runs in a container |
| Terraform | 1.16.6 (≥ 1.10 required for S3 lockfiles) | `winget install Hashicorp.Terraform` |
| AWS CLI v2 | 2.38 | `aws configure sso` |
| Session Manager plugin | 1.2.896 | `winget install Amazon.SessionManagerPlugin` (port forwarding to the recovery host) |

Memory: the full stack (Docker + browsers + editor) runs close to a 16 GB laptop's limit. See RUNBOOK §10.

## 1. Clone

```bash
git clone https://github.com/jervilangelo/bayanihan-dr.git && cd bayanihan-dr
```

## 2. System A: the cooperative CMS (local, no AWS)

```bash
cd cooperative-system
docker compose up -d --build --wait                 # PostgreSQL 16 + API on 127.0.0.1:8000, migrations run automatically
docker compose exec -T api python -m app.seed       # synthetic data: 1,050 members, 26 items, 3,000+ transactions
curl http://127.0.0.1:8000/health/ready
docker compose --profile test run --rm -T tests     # CMS test suite
```

Details: [cooperative-system/README.md](../cooperative-system/README.md).

## 3. System B part 1: local backups (no AWS)

```bash
docker compose --profile backup up -d --build                       # + verify-db + hourly scheduler
docker compose --profile backup run --rm -T backup backup           # first backup + verification now
docker compose --profile backup run --rm -T backup list
docker compose --profile backup-test run --rm -T backup-tests       # engine tests (real PostgreSQL)
```

Backups land in `backups/` (git-ignored). Details: [backend/README.md](../backend/README.md).

## 4. System C: the dashboard

```bash
cd frontend
npm ci
npm run dev            # demo mode: http://localhost:5173/bayanihan-dr/
npm run dev:ops        # operations mode: real backups from ../backups/status.json + the job runner
npm test               # unit tests
E2E_PORT=4175 npm run test:e2e -- --workers=2     # production build, Playwright (desktop + phone + axe)
```

## 5. AWS account preparation (one time, in the console)

Done with an administrator of the AWS Organization's IAM Identity Center:

1. **Permission set** `BayanihanDR-Developer-V5`:
   - AWS managed policy **`ReadOnlyAccess`**;
   - inline policy: paste [aws/bayanihandr-developer-inline-policy.json](aws/bayanihandr-developer-inline-policy.json).
     Make sure the editor's empty `Statement1` placeholder is removed;
   - session duration **4 h**.
2. **Assign** it to your user on the target account, and wait for "Provisioned".
3. **CLI profile:**
   ```bash
   aws configure sso      # SSO session name bayanihan-dr, start URL, region ap-southeast-1,
                          # role BayanihanDR-Developer-V5, profile name bayanihan-dr-dev
   aws sso login --profile bayanihan-dr-dev
   aws sts get-caller-identity --profile bayanihan-dr-dev    # must show AWSReservedSSO_BayanihanDR-Developer-V5_…
   ```
4. **Check the guardrails.** The region context is required:
   ```bash
   R=$(aws iam list-roles --path-prefix /aws-reserved/sso.amazonaws.com/ --query "Roles[?starts_with(RoleName,'AWSReservedSSO_BayanihanDR-Developer-V5')].Arn | [0]" --output text)
   MSYS_NO_PATHCONV=1 aws iam simulate-principal-policy --policy-source-arn "$R" --action-names s3:CreateBucket ec2:CreateNatGateway \
     --resource-arns "arn:aws:s3:::bayanihandr-test" --context-entries ContextKeyName=aws:RequestedRegion,ContextKeyValues=ap-southeast-1,ContextKeyType=string
   # expected: s3:CreateBucket allowed, ec2:CreateNatGateway explicitDeny
   ```

## 6. Terraform: checks without AWS

```bash
terraform fmt -recursive -check terraform
terraform -chdir=terraform/environments/recovery init -backend=false && terraform -chdir=terraform/environments/recovery validate
terraform -chdir=terraform/environments/recovery test          # 16 tests, mocked provider, no credentials
```

TFLint and Trivy commands: [terraform/README.md](../terraform/README.md#checks-run-in-phase-4).

## 7. Terraform: state bucket (bootstrap)

```bash
cd terraform/bootstrap
# First apply runs with LOCAL state: temporarily comment out `backend "s3" {}` in terraform.tf
AWS_PROFILE=bayanihan-dr-dev terraform init
AWS_PROFILE=bayanihan-dr-dev terraform plan -out=bootstrap.tfplan        # 7 to add
AWS_PROFILE=bayanihan-dr-dev terraform apply bootstrap.tfplan
```

Create `terraform/environments/recovery/backend.hcl` from `backend.example.hcl`, using the `state_bucket_name`
output. Then restore the `backend "s3" {}` block and migrate the bootstrap state into the bucket it created:

```bash
AWS_PROFILE=bayanihan-dr-dev terraform init -migrate-state -force-copy \
  -backend-config=../environments/recovery/backend.hcl -backend-config="key=bootstrap/terraform.tfstate"
AWS_PROFILE=bayanihan-dr-dev terraform plan -detailed-exitcode      # exit 0: in sync, state read from S3
```

## 8. Terraform: standby environment

```bash
cd terraform/environments/recovery
cp recovery.example.tfvars recovery.tfvars       # set budget_alert_email; keep recovery_enabled = false
AWS_PROFILE=bayanihan-dr-dev terraform init -backend-config=backend.hcl
AWS_PROFILE=bayanihan-dr-dev terraform plan -var-file=recovery.tfvars -out=standby.tfplan   # 13 to add with a budget
AWS_PROFILE=bayanihan-dr-dev terraform apply standby.tfplan
```

Confirm the AWS Budgets e-mail subscription when the e-mail arrives.

## 9. Upload-only writer role

Add the operator role ARN (`$R` from step 5.4) to `recovery.tfvars`:

```hcl
backup_writer_principal_arns = ["arn:aws:iam::<account>:role/aws-reserved/sso.amazonaws.com/ap-southeast-1/AWSReservedSSO_BayanihanDR-Developer-V5_<suffix>"]
```

```bash
AWS_PROFILE=bayanihan-dr-dev terraform plan -var-file=recovery.tfvars -out=writer.tfplan    # 2 to add
AWS_PROFILE=bayanihan-dr-dev terraform apply writer.tfplan
```

Add the CLI profile to `~/.aws/config`:

```ini
[profile bayanihan-dr-writer]
role_arn = <terraform output -raw backup_writer_role_arn>
source_profile = bayanihan-dr-dev
region = ap-southeast-1
duration_seconds = 3600
```

The permission set is reprovisioned if it is ever recreated, and then the role ARN suffix changes. Update the tfvars
and re-apply in that case.

## 10. First off-site copies

See RUNBOOK §3, then read one back to prove it:

```bash
aws s3 cp s3://<backup bucket>/backups/<id>/cms.dump - --profile bayanihan-dr-dev | sha256sum   # equals the manifest's sha256
```

## 11. Job runner and first drill

```bash
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-runner.txt
.venv/Scripts/python -m pytest runner_tests -q            # 20 tests
```

Then RUNBOOK §4–§7: start the runner, prepare a drill, approve, verify, tear down.

## 12. GitHub

- Pages: **Settings → Pages → Source: GitHub Actions**. `deploy-pages.yml` builds `frontend/` on every push that
  touches it.
- CI (`ci.yml`), the live-site check (`public-site.yml`) and Dependabot need no secrets.
- Public-site tests from any machine: `cd frontend && npm run test:public -- --workers=1`.
- Documentation screenshots: `cd frontend && node scripts/screenshots.mjs` (writes `docs/screenshots/`).
