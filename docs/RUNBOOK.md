# BayanihanDR operations runbook

Step-by-step procedures for running, drilling, recovering and tearing down BayanihanDR. Commands are shown for
**Git Bash** on Windows (the shell used throughout this project). PowerShell equivalents are given where they differ.

> **Ground rules**
> - Never run `terraform apply` or `destroy` by hand against the recovery environment unless the job runner is
>   unavailable. The runner adds the plan guard, approval and audit trail.
> - Tear down every drill once its evidence is saved. A forgotten host costs about USD 0.82/day.
> - Never commit `backend.hcl`, `recovery.tfvars`, `backend/var/`, `backups/`, `*.tfstate` or `*.tfplan` (all git-ignored).

## Contents

1. [Names and places](#1-names-and-places)
2. [Daily: check protection](#2-daily-check-protection)
3. [Take a backup and copy it off-site](#3-take-a-backup-and-copy-it-off-site)
4. [Start the job runner and the operations dashboard](#4-start-the-job-runner-and-the-operations-dashboard)
5. [Run a recovery drill](#5-run-a-recovery-drill)
6. [**Real disaster: recover the CMS into AWS**](#6-real-disaster-recover-the-cms-into-aws)
7. [Tear down a drill or recovery](#7-tear-down-a-drill-or-recovery)
8. [Set up an alternate workstation](#8-set-up-an-alternate-workstation)
9. [Inspect the recovery host](#9-inspect-the-recovery-host)
10. [Troubleshooting](#10-troubleshooting)
11. [Project end: full teardown](#11-project-end-full-teardown)
12. [Credentials and rotation](#12-credentials-and-rotation)

## 1. Names and places

| Thing | Value |
|---|---|
| AWS region | `ap-southeast-1` (Singapore) |
| SSO start URL | `https://d-9667939bda.awsapps.com/start` (session `bayanihan-dr`) |
| Operator CLI profile | `bayanihan-dr-dev` → permission set `BayanihanDR-Developer-V5` (`ReadOnlyAccess` + [inline policy](aws/bayanihandr-developer-inline-policy.json)) |
| Upload CLI profile | `bayanihan-dr-writer` → assumes `bdr-recovery-backup-writer` from `bayanihan-dr-dev` |
| Backup bucket | `bayanihandr-backups-<account>-ap-southeast-1` (`terraform output -raw backup_bucket_name`) |
| State bucket | `bayanihandr-tfstate-<account>-ap-southeast-1` |
| Log group | `/bayanihandr/recovery/recovery` (one stream per job ID) |
| Budget | `bdr-recovery-monthly-cost`, USD 10/month, e-mail alerts |
| Local settings (git-ignored) | `terraform/environments/recovery/backend.hcl`, `terraform/environments/recovery/recovery.tfvars` |
| Runner token | `backend/var/admin-token` (created on first start) |
| CMS (primary) | http://127.0.0.1:8000 (`/docs`, `/health/ready`) |
| Job runner | http://127.0.0.1:8787 |
| Operations dashboard | http://localhost:5173/bayanihan-dr/ (`npm run dev:ops`) |
| Public demo | https://jervilangelo.github.io/bayanihan-dr/ |

Docker CLI on this machine: if `docker` is not found in a new shell, run
`export PATH="$PATH:/c/Program Files/Docker/Docker/resources/bin"`.

## 2. Daily: check protection

```bash
cd cooperative-system
docker compose --profile backup ps          # db, api, verify-db, backup should be Up
docker compose --profile backup run --rm -T backup list
```

- The newest line should be `verified` and less than 1 hour old (the scheduler runs on the hour, UTC).
- A `failed` line includes the reason. A gap of whole hours means the scheduler or the host was down, and the
  dashboard shows it as **Missed**.
- The dashboard view of the same data: `cd frontend && npm run dev:ops`, then open **Overview** and **Backups**.

## 3. Take a backup and copy it off-site

The scheduler verifies backups locally every hour, but **it does not upload unattended** (ADR-013). Copy to S3 at
least daily, and always before a planned drill.

```bash
aws sso login --profile bayanihan-dr-dev                       # if the session expired (4 h)
cd cooperative-system
docker compose --profile backup run --rm -T backup backup      # optional: a fresh backup now
B=$(cd ../terraform/environments/recovery && AWS_PROFILE=bayanihan-dr-dev terraform output -raw backup_bucket_name)
eval "$(aws configure export-credentials --profile bayanihan-dr-writer --format env-no-export | sed 's/^/export /')"
BDR_OFFSITE_BUCKET="$B" docker compose --profile backup run --rm -T backup upload --all
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_CREDENTIAL_EXPIRATION
```

Expected output: one line per backup, `<id>  stored  s3://…/backups/<id>/cms.dump`. Only `verified` backups are
sent, and S3 rejects the upload if the SHA-256 does not match.

## 4. Start the job runner and the operations dashboard

```bash
aws sso login --profile bayanihan-dr-dev
cd backend
AWS_PROFILE=bayanihan-dr-dev .venv/Scripts/python -m bdr_runner      # leave running; Ctrl+C to stop
```

In a second terminal:

```bash
cd frontend && npm run dev:ops
```

Open http://localhost:5173/bayanihan-dr/#/recovery, paste the token from `backend/var/admin-token`, and sign in.
The badge shows the SSO role (`BayanihanDR-Developer-V5`).

First time on a machine: `cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-runner.txt`.

## 5. Run a recovery drill

1. Make sure a recent backup is off-site (section 3).
2. In **Recovery**, choose a recovery point and press **Prepare drill (plan only)**. The runner:
   - checks your SSO role, that no recovery host exists, and that the backup is verified **in S3**;
   - pins the CMS commit SHA;
   - runs `terraform plan` and the plan guard.
3. Review the plan. It must be **11 to add, 0 to change, 0 to destroy**, at about USD 0.034/hour. Anything else is
   refused automatically.
4. Type the job ID and press **Approve and start recovery**.
5. Watch the steps:
   - provision (~30 s);
   - Docker install (~1.5 min);
   - source, download, checksum;
   - PostgreSQL and restore (~1 min);
   - CMS build and start (~1 min);
   - health, record counts.

   A typical total is 5–7 minutes.
6. Optional, but recommended: an independent check (section 9).
7. Record the result. The job JSON is in `backend/var/jobs/<job-id>/job.json`. For a formal drill, copy the numbers
   into a new file under `docs/evidence/`, following `phase7-disaster-drill.md`.
8. **Tear down** (section 7).

The same through the API, for scripting:

```bash
T=$(tr -d '\r\n' < backend/var/admin-token); H="Authorization: Bearer $T"
curl -s -H "$H" http://127.0.0.1:8787/api/recovery-points
curl -s -X POST -H "$H" -H 'Content-Type: application/json' -d '{"type":"recovery-drill","backup_id":"<ID>"}' http://127.0.0.1:8787/api/jobs
curl -s -H "$H" http://127.0.0.1:8787/api/jobs/<JOB>                    # wait for "awaiting-approval"
curl -s -X POST -H "$H" -H 'Content-Type: application/json' -d '{"confirm_job_id":"<JOB>"}' http://127.0.0.1:8787/api/jobs/<JOB>/approve
curl -s -H "$H" http://127.0.0.1:8787/api/audit
```

## 6. Real disaster: recover the CMS into AWS

Use this when the office server is unavailable. You need a laptop with Git, Terraform ≥ 1.10, the AWS CLI v2,
Python 3.12+, Node 22 (only for the dashboard), and your SSO sign-in.

1. **Declare the incident.** Write down the time the office went down (T_disaster) and the time you start (T_declared).
2. **Get a workstation ready.** Use your usual laptop, or prepare another one (section 8, about 5 minutes).
3. **Sign in:** `aws sso login --profile bayanihan-dr-dev`.
4. **Start the runner** (section 4). The dashboard is optional: everything also works through the API.
5. **Pick the newest off-site recovery point:** Recovery page, or `GET /api/recovery-points`. These come from S3,
   not from the office.
6. **Prepare, review, approve** (section 5, steps 2–5).
7. **Verify independently** (section 9): `/health/ready`, record totals, and a few known members.
8. **Hand over:**
   - Users reach the recovered CMS through an SSM port forward (section 9).
   - Exposing it more widely, for example with a load balancer or public ingress, is **out of scope for v1** and
     would need a security review. It is explicitly denied by the operator policy (no load balancers).
9. **Record:** RTO = T_verified − T_declared; RPO = T_disaster − backup time.
10. **Return to the office** once power is back: start the primary (`docker compose start` in
    `cooperative-system`), confirm `/health/ready`, then tear down the recovery environment (section 7).
    Data entered on the recovery host during the outage **is not copied back automatically**. Export it first
    (`pg_dump` on the host, through SSM) if it must be kept.

## 7. Tear down a drill or recovery

Through the runner (preferred):
1. **Recovery → Prepare teardown (plan only).**
2. The plan must be **0 to add, 0 to change, 11 to destroy**. The guard refuses anything that touches the backups,
   IAM or the budget.
3. Type the job ID, then approve.
4. The runner confirms that no recovery host remains.

Independent confirmation:

```bash
export AWS_PROFILE=bayanihan-dr-dev
aws ec2 describe-instances --filters Name=tag:Project,Values=BayanihanDR Name=instance-state-name,Values=pending,running,stopping,stopped --query 'length(Reservations)'   # 0
aws ec2 describe-vpcs --filters Name=tag:Project,Values=BayanihanDR --query 'length(Vpcs)'                                                                            # 0
cd terraform/environments/recovery && terraform plan -var-file=recovery.tfvars -detailed-exitcode   # exit 0 = standby, no changes
```

The Resource Groups Tagging API (and the console's Tag Editor) keeps listing deleted instances, volumes and
security groups for a while. Trust `describe-*` calls instead.

**Emergency teardown without the runner** (the runner is broken and a host is running):

```bash
cd terraform/environments/recovery
AWS_PROFILE=bayanihan-dr-dev terraform plan -var-file=recovery.tfvars -var recovery_enabled=false -out=td.tfplan
# READ the plan: only module.networking[0].*, module.compute[0].*, and the status alarm may be destroyed
AWS_PROFILE=bayanihan-dr-dev terraform apply td.tfplan
```

## 8. Set up an alternate workstation

Recovery must not depend on the office or on one particular laptop. Phase 7 used exactly these steps.

```bash
git clone https://github.com/jervilangelo/bayanihan-dr.git && cd bayanihan-dr
# Copy in the two local settings files, from your password manager or another operator:
#   terraform/environments/recovery/backend.hcl     (state bucket name, key, region, use_lockfile = true)
#   terraform/environments/recovery/recovery.tfvars (recovery_enabled = false, budget e-mail, writer principal)
aws configure sso          # session bayanihan-dr, start URL above, region ap-southeast-1,
                           # role BayanihanDR-Developer-V5, profile name bayanihan-dr-dev
aws sso login --profile bayanihan-dr-dev
cd terraform/environments/recovery && AWS_PROFILE=bayanihan-dr-dev terraform init -backend-config=backend.hcl && cd -
cd backend && python -m venv .venv && .venv/Scripts/pip install -r requirements-runner.txt
```

Keep a copy of `backend.hcl` and `recovery.tfvars` somewhere that survives the office, such as a password manager.
They hold no secrets, only the bucket name (which contains the account ID) and an e-mail address.

## 9. Inspect the recovery host

Install the Session Manager plugin once: `winget install Amazon.SessionManagerPlugin`.

```bash
export PATH="$PATH:/c/Program Files/Amazon/SessionManagerPlugin/bin" AWS_PROFILE=bayanihan-dr-dev
I=$(aws ec2 describe-instances --filters Name=tag:JobId,Values=<JOB> Name=instance-state-name,Values=running --query 'Reservations[0].Instances[0].InstanceId' --output text)

# Shell on the host (logs: /var/log/bayanihandr-restore.log; containers: sudo docker ps)
aws ssm start-session --target "$I"

# Port forward: the recovered CMS on http://127.0.0.1:18000 of this workstation
aws ssm start-session --target "$I" --document-name AWS-StartPortForwardingSession \
  --parameters '{"portNumber":["8000"],"localPortNumber":["18000"]}'
curl -s http://127.0.0.1:18000/health/ready
curl -s 'http://127.0.0.1:18000/api/v1/farmers?limit=1'      # "total" = member count
```

Host progress events without a shell:

```bash
MSYS_NO_PATHCONV=1 aws logs get-log-events --log-group-name /bayanihandr/recovery/recovery --log-stream-name <JOB> --start-from-head --query 'events[].message' --output text
```

## 10. Troubleshooting

| Symptom | Likely cause | What to do |
|---|---|---|
| `Unable to locate credentials` / `ExpiredToken` / runner preflight "wrong identity" | SSO session expired (4 h) or wrong profile | `aws sso login --profile bayanihan-dr-dev`, then restart the runner with `AWS_PROFILE=bayanihan-dr-dev` |
| Preflight: "N recovery host(s) already exist" | A previous drill or a failed drill was not torn down | Run a teardown job (section 7) |
| Preflight: "not a verified off-site backup" | The point is only local, or its manifest is not `verified` | Upload it (section 3) or choose another point |
| Plan rejected: "outside the drill footprint" | State drift, or the Terraform code changed | Do **not** approve. Run `terraform plan -var-file=recovery.tfvars` and investigate before anything else |
| `Error acquiring the state lock` | Another plan or apply is running, or one crashed | Wait. If it is certainly stale: `terraform force-unlock <ID>` (the ID is in the error) |
| Job failed at `verify-checksum` | The off-site object does not match its manifest (corruption or tampering) | Working as designed. Tear down, check S3 object versions, and choose another recovery point |
| Job failed at `health` or `start-app` | CMS build or start problem on the host | Look at `/var/log/bayanihandr-restore.log` and `sudo docker logs bdr-cms-api` (section 9), then tear down |
| Job "no verified recovery within 30 minutes" | Host stuck (package mirror, Docker Hub rate limit) | Inspect through SSM. Tear down |
| A failed job left a host running | By design, failures do not auto-teardown | Teardown job (section 7) |
| Runner restarted mid-job | The job is marked failed: "resources may exist" | Check AWS (section 7) and tear down |
| `docker run` / `docker compose run` hangs, containers stuck in "Created" | Windows commit memory exhausted, or Docker Desktop wedged | Close memory-heavy apps. `docker desktop restart` (CMS containers restart themselves) |
| Node/Vite/tsc: "Zone Allocation failed", browsers crash in tests | Windows commit memory near its limit (24 GB) | Free memory. Run e2e with `--workers=1` |
| Playwright: port 4174 already used | Another local project (pinansyalph) uses it | `E2E_PORT=4175 npm run test:e2e` |
| Git Bash turns `/aws/...` or `/bayanihandr/...` into Windows paths | MSYS path conversion | Prefix the command with `MSYS_NO_PATHCONV=1` |
| IAM policy simulator says `explicitDeny` for a project action | The region guardrail needs the region in context | Add `--context-entries ContextKeyName=aws:RequestedRegion,ContextKeyValues=ap-southeast-1,ContextKeyType=string` |
| CI e2e failed but passes locally | Timing differences on Linux runners | Reproduce with `docker run --rm --ipc=host -v "$PWD/frontend:/src:ro" mcr.microsoft.com/playwright:v1.64.1-noble …` (see CHANGELOG Phase 9) |

## 11. Project end: full teardown

Not done yet. The standby environment is kept on purpose (owner's decision, 2026-11-05). The reviewed destroy plan
is in [evidence/phase10-inventory.md](evidence/phase10-inventory.md). Order matters:

1. Confirm no drill is running (section 7). If one is, tear it down first.
2. **Empty the backup bucket, including all object versions.** `force_destroy = false` blocks deletion otherwise.
   Keep a local copy first if you want one.
   ```bash
   B=$(cd terraform/environments/recovery && terraform output -raw backup_bucket_name)
   aws s3 cp --recursive s3://$B/backups/ ./final-offsite-copy/           # optional keepsake
   AWS_PROFILE=bayanihan-dr-dev backend/.venv/Scripts/python - "$B" <<'EOF'   # the runner's venv has boto3
   import boto3, sys
   boto3.resource("s3").Bucket(sys.argv[1]).object_versions.delete()      # deletes ALL versions
   EOF
   ```
3. Destroy the environment and **review the plan** (15 to destroy: bucket, roles, log group, budget):
   `terraform plan -destroy -var-file=recovery.tfvars -out=destroy.tfplan`, then `terraform apply destroy.tfplan`.
4. State bucket:
   - Its `prevent_destroy` must be removed deliberately: edit `terraform/bootstrap/main.tf`.
   - Migrate the bootstrap state back to local: comment out `backend "s3" {}`, then
     `terraform init -migrate-state`.
   - Empty the bucket (all versions), then `terraform destroy` in `terraform/bootstrap`.
5. IAM Identity Center:
   - delete the permission sets `BayanihanDR-Developer-V5` and the unused `BayanihanDR-Developer`;
   - remove the `bayanihan-dr-*` profiles from `~/.aws/config` (a backup exists at `~/.aws/config.bak-20261105`).
6. Check for residual charges after 24–48 h: Cost Explorer, filtered to ap-southeast-1, should show no EC2, VPC,
   S3 or CloudWatch charges for the project.
7. The public demo on GitHub Pages keeps working with AWS gone. It never calls AWS.

## 12. Credentials and rotation

| Credential | Lifetime | Rotation |
|---|---|---|
| SSO session (`bayanihan-dr-dev`) | 4 h | `aws sso login`; revoke by removing the account assignment in Identity Center |
| Writer role credentials | 1 h | Requested per upload; never stored |
| Recovery host role | Instance lifetime (short-lived STS credentials from IMDSv2) | Destroyed with the host |
| Runner admin token | Until the file is deleted | Stop the runner, delete `backend/var/admin-token`, start it again (a new token is generated) |
| CMS database password (office) | `.env` (git-ignored); development default otherwise | Change `POSTGRES_PASSWORD` in `cooperative-system/.env`, then recreate the containers |
| CMS database password (recovery host) | Generated at boot, never leaves the host | Destroyed with the host |

There are **no long-lived AWS access keys anywhere** in this project. The operator policy denies creating IAM users and access keys.
