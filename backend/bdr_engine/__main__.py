"""Command line: ``python -m bdr_engine <command>``.

Commands are a fixed allowlist. None of them accept SQL, shell or file-path arguments.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import ConfigError, Settings
from .jobs import backup_and_verify, prune, write_status
from .manifest import is_backup_id
from .offsite import OffsiteError, default_client, upload_backup
from .scheduler import run_forever
from .store import BackupStore, EngineBusy
from .verify import VerifyError, verify_backup

ACTOR = "Operator (CLI)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bdr_engine", description="BayanihanDR backup engine")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("backup", help="create a backup now, then verify it")
    v = sub.add_parser("verify", help="re-verify one backup, or every backup with --all")
    v.add_argument("backup_id", nargs="?")
    v.add_argument("--all", action="store_true")
    sub.add_parser("list", help="list backups and their state")
    p = sub.add_parser("prune", help="show (or with --apply, perform) retention deletions")
    p.add_argument("--apply", action="store_true")
    u = sub.add_parser("upload", help="copy verified backups to the off-site S3 bucket")
    u.add_argument("backup_id", nargs="?")
    u.add_argument("--all", action="store_true", help="every verified backup not yet stored off-site")
    sub.add_parser("status", help="write status.json for the dashboard")
    s = sub.add_parser("schedule", help="run the scheduler until stopped")
    s.add_argument("--run-now", action="store_true", help="also back up immediately on start")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        settings = Settings.from_env()
    except ConfigError as e:
        print(f"configuration error: {e}", file=sys.stderr)
        return 2
    store = BackupStore(settings.backup_dir)

    try:
        if args.command == "backup":
            m = backup_and_verify(settings, store, trigger="manual", actor=ACTOR)
            write_status(settings, store)
            print(f"{m['backup_id']}  {m['status']}  {m['failure_reason'] or ''}".rstrip())
            return 0 if m["status"] == "verified" else 1
        if args.command == "verify":
            if args.all == bool(args.backup_id):
                parser.error("give one backup ID or --all")
            if args.backup_id and not is_backup_id(args.backup_id):
                parser.error("backup IDs look like 20261104T070000Z")
            failures = 0
            with store.lock():
                ids = [e.backup_id for e in store.entries() if e.manifest and e.manifest["archive"]["sha256"]] if args.all else [args.backup_id]
                for backup_id in ids:
                    try:
                        m = verify_backup(settings, store, backup_id, actor=ACTOR)
                        print(f"{backup_id}  {m['status']}  {m['failure_reason'] or ''}".rstrip())
                        failures += m["status"] != "verified"
                    except VerifyError as e:
                        print(f"{backup_id}  rejected  {e}")
                        failures += 1
            write_status(settings, store)
            return 0 if failures == 0 else 1
        if args.command == "list":
            for e in store.entries():
                if e.manifest is None:
                    print(f"{e.backup_id}  untrusted  {e.error}")
                    continue
                m = e.manifest
                size = m["archive"]["size_bytes"]
                print(f"{e.backup_id}  {m['status']:<11} {m['trigger']:<9} {size or 0:>10,} B  {m['failure_reason'] or ''}".rstrip())
            return 0
        if args.command == "prune":
            for d in prune(settings, store, apply=args.apply, actor=ACTOR):
                print(f"{d.backup_id}  {'keep  ' if d.keep else ('DELETE' if args.apply else 'would delete')}  {d.reason}")
            write_status(settings, store)
            return 0
        if args.command == "upload":
            if args.all == bool(args.backup_id):
                parser.error("give one backup ID or --all")
            if args.backup_id and not is_backup_id(args.backup_id):
                parser.error("backup IDs look like 20261104T070000Z")
            if not settings.offsite_bucket:
                print("off-site upload is not configured (BDR_OFFSITE_BUCKET)", file=sys.stderr)
                return 2
            client = default_client(settings.aws_region)
            failures = 0
            with store.lock():
                ids = (
                    [e.backup_id for e in store.entries() if e.manifest and e.manifest["status"] == "verified" and e.manifest["offsite"] != "stored"]
                    if args.all
                    else [args.backup_id]
                )
                for backup_id in ids:
                    try:
                        m = upload_backup(store, backup_id, bucket=settings.offsite_bucket, prefix=settings.offsite_prefix, client=client, actor=ACTOR)
                        print(f"{backup_id}  stored  s3://{settings.offsite_bucket}/{m['offsite_detail']['key']}")
                    except OffsiteError as e:
                        print(f"{backup_id}  not uploaded  {e}")
                        failures += 1
            write_status(settings, store)
            return 0 if failures == 0 else 1
        if args.command == "status":
            status = write_status(settings, store)
            print(json.dumps({k: status[k] for k in ("generatedAt", "primary")} | {"backups": len(status["backups"])}, indent=2))
            return 0
        if args.command == "schedule":
            run_forever(settings, store, run_now=args.run_now)
            return 0
    except EngineBusy as e:
        print(f"busy: {e}", file=sys.stderr)
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(main())
