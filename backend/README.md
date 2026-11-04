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

Backups are written to `<repo>/backups/`, which is git-ignored and never committed. To see them in the dashboard,
run `npm run dev:ops` in `frontend/`.

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

## Limits (Phase 3)

- Backups live on the same machine as the primary. Off-site copies (S3, encrypted) arrive in Phase 5. Until then this
  protects against corruption and bad changes, not against losing the office.
- A manifest is trusted as written. Someone who can rewrite both the archive and its manifest can forge a backup.
  S3 Object Lock or signed manifests are possible later hardening.
- The engine image runs as the `postgres` user (uid 70). On a Linux host, `backups/` must be writable by that UID.
