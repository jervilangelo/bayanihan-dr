# BayanihanDR cost

Planning budget (blueprint §16): **PHP 300–500** for all AWS testing. That is a planning figure, not a hard cap.
**Actual project spend so far: well under USD 0.10 (under PHP 6).**

## 1. Verified prices (AWS Pricing API, ap-southeast-1, on-demand, 2026-11-05)

| Item | Price |
|---|---|
| EC2 t3.small (Linux) | USD 0.0264 / hour |
| EC2 t3.micro / t3.medium | USD 0.0132 / 0.0528 per hour |
| Public IPv4 address (in use or idle) | USD 0.005 / hour |
| EBS gp3 | USD 0.096 / GB-month |
| S3 Standard storage (first 50 TB) | USD 0.025 / GB-month |
| CloudWatch alarm (standard resolution) | USD 0.10 / alarm-month |
| S3 gateway endpoint | free |
| AWS Budgets (cost budget with e-mail alerts) | not billed for this use |

Re-check prices before any large change: `aws pricing get-products --region us-east-1 --service-code AmazonEC2 --filters Type=TERM_MATCH,Field=regionCode,Value=ap-southeast-1 …`
(full commands in the Phase 5 history, `docs/evidence/phase5-deployment.md`).

## 2. What runs, and what it costs

| Footprint | Resources | Cost |
|---|---|---|
| **Standby** (always on, current state) | 2 S3 buckets (backups, state), 2 IAM roles + instance profile, 1 log group, 1 budget | **≈ USD 0.01/month or less**: about 0.2 MB of backups and state, plus a few hundred requests per month |
| **Drill / recovery** (only while running) | VPC, subnet, IGW, routes, S3 endpoint, 2 security groups, t3.small host with 20 GiB gp3, public IPv4, status alarm | **≈ USD 0.0342/hour ≈ USD 0.82/day** |

The drill rate is computed by the job runner from the plan (`planguard.estimate_hourly`):
0.0264 (t3.small) + 0.005 (IPv4) + 20 × 0.096 / 730 (gp3) + 0.10 / 730 (alarm) = **USD 0.0342/h**.

Not used at all: NAT Gateway (≈ USD 0.059/h + data), RDS, load balancers, EKS, Elastic IPs, KMS keys. The operator
policy explicitly denies most of them.

## 3. Actual drills

| Drill | Host lifetime | Cost at the computed rate |
|---|---|---|
| Phase 6 first drill (+ teardown) | 06:17:45 → 06:23:53 (≈ 6 min) | ≈ USD 0.0035 |
| Phase 7 disaster drill (+ teardown) | 06:32:45 → 06:39:06 (6 min 21 s) | ≈ USD 0.0036 |
| Phase 7 corrupted-backup drill (+ teardown) | 06:40:33 → 06:45:44 (5 min 11 s) | ≈ USD 0.0030 |
| **Total** | ≈ 17.5 min | **≈ USD 0.010 (≈ PHP 0.60)** |

EC2 bills per second (60-second minimum per launch), so these estimates are close to the real charge.

## 4. Billing records (Cost Explorer, whole account, November 2026 to date)

As of 2026-11-05 15:40 PHT:

| Service | Month to date (USD) | Belongs to |
|---|---|---|
| Amazon S3 | 0.00109 | BayanihanDR (buckets, uploads, state); may include other projects' S3 |
| Amazon CloudWatch | 0.00004 | BayanihanDR log group |
| AWS Amplify, AppSync, DynamoDB | 0.1200 | **another project** (not BayanihanDR) |
| Tax | 0.01 | account |
| EC2 / VPC for the 2026-11-05 drills | **not yet billed** | Cost Explorer lags by up to 24 h. Expect ≈ USD 0.01 to appear |

Account month-to-date: USD 0.1269 before Phase 7, USD 0.1312 after. **Re-check after 2026-11-06** to confirm the drill
charges landed as estimated:

```bash
aws ce get-cost-and-usage --region us-east-1 --time-period Start=2026-11-01,End=2026-12-01 --granularity MONTHLY \
  --metrics UnblendedCost --group-by Type=DIMENSION,Key=SERVICE --profile bayanihan-dr-dev
```

## 5. Budget alerts

- `bdr-recovery-monthly-cost`: USD 10/month. E-mail at 50% actual, 100% actual and 100% forecast. This is the
  project's own budget; the account also has other budgets from other projects.
- **Alerts never stop charges.** The protections that actually limit spend are:
  - the standby-by-default design;
  - the plan guard;
  - `instance_initiated_shutdown_behavior = terminate`;
  - T3 standard credits (no unlimited-mode surcharge);
  - the operator policy's denies;
  - tearing down after every drill.

## 6. Cost risks to watch

| Risk | Typical cost | Guard |
|---|---|---|
| A drill host left running | USD 0.82/day | Teardown after every drill; budget alert; `describe-instances` in the daily check (RUNBOOK §2) |
| A failed drill leaves its host | same | Runner message + RUNBOOK; auto-teardown is an open item |
| Many backups with versioning | Negligible at about 97 KB each | Lifecycle: 30 days current, 7 days noncurrent |
| A larger real database | S3 at USD 0.025/GB-month | Lifecycle rules |
| Data transfer | Downloads to the host use the free gateway endpoint; uploads to S3 are free | n/a |
