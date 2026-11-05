# BayanihanDR security

What is protected, against what, and how. Every control listed here is implemented and tested, unless it is marked
**accepted risk** or **open**. Requirements: blueprint §11. Decisions: ADR-011 to ADR-015.

## 1. What we protect

| Asset | Why it matters |
|---|---|
| Off-site backups (S3) | The only way back after losing the office. Must survive a compromised or destroyed office server. |
| Terraform state (S3) | Losing it orphans real, billed resources; tampering could redirect a recovery. |
| AWS account | Unbounded spend or data exposure if misused. |
| Recovery host | Runs the restored CMS. Must not be reachable from the internet. |
| Operator workstation | Holds the SSO session and the runner token during a recovery. |
| Public site | Must not leak operational details, and must not be able to reach AWS. |

All data is **synthetic** (blueprint §11.1). No real member, financial or personal data is stored anywhere.

## 2. Threats and controls

| Threat | Controls | Evidence |
|---|---|---|
| Ransomware or an attacker on the office server deletes or encrypts backups | The engine uploads with role `bdr-recovery-backup-writer`: **`s3:PutObject` only**, on `backups/*` only. It cannot list, read or delete. S3 **versioning** keeps any overwritten object; noncurrent versions are kept 7 days. | phase5-deployment.md: list, delete and write outside `backups/` all return `AccessDenied` |
| A corrupted or tampered backup is restored | The manifest carries a SHA-256; S3 checks `ChecksumSHA256` on upload; the recovery host re-checks the SHA-256 against the **verified** manifest before restoring, and fails closed. Locally, every backup is test-restored and its record counts compared. | phase7-disaster-drill.md (P8): a 1-byte corruption was refused before any restore |
| A recovery restores the wrong thing, or runs unreviewed infrastructure | The job runner pins the backup ID and CMS commit SHA. The plan guard allows only the 11 drill resources (creates) or their removal (deletes). The **saved** plan file is applied. A human types the job ID to approve. | runner_tests: unexpected plan rejected; wrong confirmation rejected |
| A browser page or another local process drives the job runner | Listens on 127.0.0.1 only. Random bearer token (constant-time comparison). Host-header allowlist (DNS rebinding). Origin allowlist (CSRF). No CORS. Only two job types. | runner_tests: 401 without token, 403 for foreign Origin, 400 for foreign Host |
| Command or parameter injection through the API | Pydantic validation with strict patterns. Terraform variables pass through an allowlist with per-variable format checks. Fixed command lines, with no shell. | runner_tests: `"../../etc"` and `"latest; rm -rf /"` rejected |
| The recovery host is attacked from the internet | Security group with **no inbound rules** and outbound TCP 443 only. The default security group has no rules. No SSH keys; access through **SSM Session Manager** only. | Terraform tests: network module assertions |
| A container on the host steals AWS credentials | **IMDSv2 required, hop limit 1**. The instance role can only read `backups/*`, write its own log group, and use SSM. | Terraform tests: compute module assertions |
| An operator's mistake creates expensive or dangerous resources | Operator inline policy: writes only to `bayanihandr-*` and `bdr-*` resources. **Explicit deny** on NAT gateways, Elastic IPs, reserved or dedicated capacity, RDS, load balancers, EKS, IAM users, access keys and login profiles, and any region except ap-southeast-1. Instance types limited to t3.micro/small/medium. | IAM policy simulator results (phase5-deployment.md); IAM Access Analyzer: 0 findings |
| Long-lived credentials leak | None exist. SSO sessions last 4 h; writer credentials 1 h and are never written to disk; instance credentials come from IMDSv2. Creating IAM users and keys is denied. | inline policy; RUNBOOK §12 |
| Secrets or account details committed to Git | `.gitignore` covers `.env*`, `*.tfstate`, `*.tfplan`, `*.tfvars` (except `*.example.tfvars`), `backend.hcl`, `backups/`, `backend/var/`. Every commit in this project was scanned for account IDs, e-mail addresses and AWS key patterns before pushing. | commit history |
| A malicious pull request or compromised action reaches AWS | CI has **no AWS credentials**, `contents: read`, `persist-credentials: false`, and actions pinned to commit SHAs. Dependabot proposes updates. | ADR-015 |
| The public site leaks operations or contacts AWS | The production bundle drops all operations-mode code (`import.meta.env.DEV`). CI greps the bundle for runner code. The published drill data has a sanitization test (account IDs, IPs, instance IDs, bucket names, e-mails, ARNs). Playwright fails on any request leaving the site, on the local build and on the live site. | CI dashboard job; `npm run test:public` |
| Terraform state is lost or corrupted | Versioned, encrypted, private, TLS-only state bucket with `prevent_destroy`. S3 lockfiles. Noncurrent state versions kept 30 days. | terraform/bootstrap |
| Data in transit or at rest is exposed | Both buckets: SSE-S3, `DenyInsecureTransport` policy, all four public-access blocks, ACLs disabled. EBS root volume encrypted. | phase5-deployment.md inventory |

## 3. Accepted risks (cost trade-offs, ADR-012)

| Finding | Why accepted | Revisit when |
|---|---|---|
| SSE-S3 instead of a customer-managed KMS key (Trivy AWS-0132) | A KMS key costs about USD 1/month plus requests, a large share of the budget; the data is synthetic | Real data, or a compliance requirement |
| CloudWatch Logs without a CMK (AWS-0017) | Logs are already encrypted by default | Same |
| No S3 access logging (AWS-0089) | Needs another bucket and costs storage; CloudTrail management events cover configuration changes | An audit requirement for object-level access |
| The host verifies its own restore | The independent SSM check exists and was used in Phase 7, but it is not automated in the runner | Automating it in the runner |
| A manifest is trusted as written | Someone who can rewrite both archive and manifest in S3 could forge a backup; the writer role cannot read or overwrite without leaving a version | S3 Object Lock or signed manifests |

## 4. Open items

1. **Unattended off-site upload.** Uploads need an operator session (ADR-013). Long-lived workload identity such as
   **IAM Roles Anywhere** would let the office scheduler upload hourly without keys.
2. **Failed drills do not auto-teardown.** A failed job leaves its host running until a teardown job is run.
3. **Users of the recovered CMS** can only reach it through SSM port forwarding. Wider access needs a reviewed design;
   load balancers are denied today.

## 5. If something goes wrong

| Event | First actions |
|---|---|
| Runner token exposed | Stop the runner, delete `backend/var/admin-token`, restart (a new token is generated) |
| SSO account compromised | In IAM Identity Center, remove the account assignment for the user; check CloudTrail for `bdr-*` and `bayanihandr-*` activity |
| Unexpected AWS spend | Budget e-mail arrives → `aws ec2 describe-instances --filters Name=tag:Project,Values=BayanihanDR`, then a teardown job (RUNBOOK §7) |
| Suspected backup tampering | Do not restore. Compare S3 object versions with the manifests (`aws s3api list-object-versions`); restore a known-good version; choose another recovery point |
