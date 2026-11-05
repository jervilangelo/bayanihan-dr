# BayanihanDR recovery engine (System B)

Phase 3 covers local backup and restore verification. Recovery orchestration (Terraform, AWS, an authenticated job
runner) comes in Phase 6 and will live in this folder too.

## What it does

Every hour, on the hour:

1. **Backup.** `pg_dump` (custom format) of the CMS database. Record counts and the schema revision are read in the
   same `REPEATABLE READ` snapshot that `pg_dump` uses, so the manifest describes exactly what is in the archive,
   even while the CMS keeps writing.
2. **Manifest.** ID (UTC start time, for example `20261104T070000Z`), timestamps, trigger, PostgreSQL and
   `pg_dump` versions, schema revision, size, SHA-256 and record counts. It is written atomically.
3. **Verify.** All five checks must pass:
   - the archive file is present;
   - its SHA-256 matches the manifest;
   - `pg_restore --list` can read it;
   - it restores into a **disposable** PostgreSQL database (RAM-only container);
   - the schema revision and every record count match the manifest.

   Only then is the backup `verified`. Anything else is `failed` and is never offered as a recovery point.
4. **Retain.**
   - Keep everything for 24 hours.
   - After that, keep the newest verified backup per UTC day for 7 days.
   - The newest verified backup is **never** deleted. In-progress backups are never touched.
5. **Report.** It writes `status.json` for the dashboard's local operations mode and appends to `events.jsonl`.

It also detects and reports:
- a failed `pg_dump` (a failed manifest with no archive);
- a corrupted, truncated or tampered archive;
- a missing or unreadable manifest;
- a backup that never finished;
- a verified archive deleted later;
- missed schedule slots;
- concurrent jobs (refused with a file lock).

## Run it (from `cooperative-system/`)

```bash
docker compose --profile backup up -d --build         # CMS + verify-db + hourly scheduler
docker compose --profile backup run --rm -T backup backup         # back up and verify now
docker compose --profile backup run --rm -T backup list
docker compose --profile backup run --rm -T backup verify --all   # re-verify everything
docker compose --profile backup run --rm -T backup prune          # dry run; add --apply to delete
docker compose --profile backup-test run --rm -T backup-tests     # engine test suite
```

### Off-site copies (Phase 5)

```bash
# 1-hour credentials for the upload-only role, exported into this shell only (never written to a file)
eval "$(aws configure export-credentials --profile bayanihan-dr-writer --format env-no-export | sed 's/^/export /')"
BDR_OFFSITE_BUCKET=<backup bucket> docker compose --profile backup run --rm -T backup upload --all
```

`upload` sends only `verified` backups. It sends the archive first, then the manifest, each with a SHA-256 that S3
checks on arrival. The manifest then records `offsite: stored` with the S3 version ID; a failure is recorded as
`rejected`. The writer role can add objects but cannot list, read or delete them.

Backups are written to `<repo>/backups/`, which is git-ignored and never committed. To see them in the dashboard,
run `npm run dev:ops` in `frontend/`.

## Recovery job runner (Phase 6)

`bdr_runner` is a local, authenticated API on the operator's trusted workstation. It runs **real recovery drills**
into AWS through a bounded Terraform workflow (blueprint §10). It needs nothing from the office server: recovery
points, Terraform state and logs all live in AWS.

```bash
cd backend
python -m venv .venv && .venv/Scripts/pip install -r requirements-runner.txt   # Windows path; bin/ on Linux
aws sso login --profile bayanihan-dr-dev
AWS_PROFILE=bayanihan-dr-dev .venv/Scripts/python -m bdr_runner   # http://127.0.0.1:8787
cd ../frontend && npm run dev:ops   # Recovery page -> paste the token from backend/var/admin-token
```

| Step | What happens | Fails closed when |
|---|---|---|
| Preflight | Checks the SSO role, that no recovery host exists, that the backup is verified **off-site**, and pins the CMS commit SHA | Wrong role, a drill already running, the point not in S3 |
| Plan | `terraform plan` with validated variables only; the plan guard checks every planned change | Anything outside the drill footprint, any update or replace, no host planned |
| Approval | The job waits; an administrator must type the job ID | Wrong ID: nothing is applied |
| Provision | `terraform apply` of the saved plan file (exactly what was reviewed) | Apply error: the job fails with Terraform's message |
| Restore | The host reports each step to CloudWatch Logs: install, fetch app, download, SHA-256, start DB, restore, start CMS, health, record counts | Any host step fails, or no verified recovery within 30 min |
| Report | RTO (declared → verified), RPO (declared − backup time), step durations | n/a |
| Teardown | A separate job: the plan may only **delete** drill resources, it needs its own approval, and it confirms no hosts remain | Plan touches backups, IAM or the budget |

Security:
- binds to 127.0.0.1 only, with Host-header and Origin checks;
- a random bearer token, created on first start in `backend/var/admin-token` (git-ignored), compared in constant time;
- two job types only, and a backup ID matching a strict pattern;
- no SQL, shell commands, paths or Terraform arguments from requests;
- only one active job at a time;
- every action goes to `backend/var/jobs/audit.jsonl`;
- a job that was active when the runner stopped is marked failed on restart, never resumed blindly.

## Configuration (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `BDR_SOURCE_HOST/PORT/USER/PASSWORD/DB` | (required) | The CMS database to back up |
| `BDR_VERIFY_HOST/PORT/USER/PASSWORD` | (required) | Disposable server used for test restores |
| `BDR_BACKUP_DIR` | `/backups` | Backup store |
| `BDR_INTERVAL_MINUTES` | `60` | Schedule interval |
| `BDR_RPO_MINUTES` / `BDR_RTO_MINUTES` | `60` / `30` | Targets reported to the dashboard |
| `BDR_KEEP_ALL_HOURS` / `BDR_KEEP_DAILY_DAYS` | `24` / `7` | Retention |
| `BDR_TABLES` | `farmers,inventory_items,transactions` | Tables whose counts are checked |

Passwords are only read from the environment, and they reach `pg_dump` and `pg_restore` through `PGPASSWORD`.
They never appear on a command line. The CLI accepts a fixed set of commands; none of them take SQL, shell commands
or file paths.

## Limits

- Off-site copies are made manually with `upload --all` (see above). The scheduler does not upload unattended yet:
  that needs long-lived workload credentials (Phase 6).
- A manifest is trusted as written. Someone who can rewrite both the archive and its manifest can forge a backup.
  S3 Object Lock or signed manifests are possible later hardening.
- The engine image runs as the `postgres` user (uid 70). On a Linux host, `backups/` must be writable by that UID.
