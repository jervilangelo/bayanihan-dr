"""Proves a backup is restorable by restoring it into a disposable database and checking the data.

A matching checksum or a successful upload is not proof (blueprint §9). Only a backup that passes every
check below is marked ``verified``; anything else is ``failed`` and never offered as a recovery point.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from datetime import datetime
from typing import Any

import psycopg

from . import pg
from .config import Settings
from .manifest import ManifestError, iso, sha256_file, utcnow
from .store import BackupStore


class VerifyError(RuntimeError):
    pass


def _check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> bool:
    checks.append({"name": name, "ok": ok, "detail": detail})
    return ok


def verify_backup(
    settings: Settings,
    store: BackupStore,
    backup_id: str,
    *,
    actor: str = "Operator (CLI)",
    now: Callable[[], datetime] = utcnow,
) -> dict[str, Any]:
    try:
        manifest = store.read_manifest(backup_id)
    except ManifestError as e:
        store.log_event(severity="error", title="Backup rejected", detail=f"Cannot verify: {e}", actor=actor, backup_id=backup_id)
        raise VerifyError(f"backup {backup_id} cannot be verified: {e}") from e
    if manifest["status"] == "in-progress":
        raise VerifyError(f"backup {backup_id} has not finished")
    if manifest["archive"]["sha256"] is None:
        raise VerifyError(f"backup {backup_id} has no archive (the backup itself failed)")

    checks: list[dict[str, Any]] = []
    result = {"checksum": "not-run", "restore_test": "not-run", "restore_seconds": None}
    archive = store.archive_path(backup_id)
    expected = manifest["records"]
    ok = _check(checks, "archive-present", archive.exists(), "Archive file found" if archive.exists() else "Archive file is missing")

    if ok:
        sha, size = sha256_file(archive)
        match = sha == manifest["archive"]["sha256"] and size == manifest["archive"]["size_bytes"]
        result["checksum"] = "match" if match else "mismatch"
        ok = _check(
            checks,
            "checksum",
            match,
            "SHA-256 matches the manifest" if match else f"SHA-256 does not match the manifest ({size:,} bytes on disk)",
        )

    if ok:
        try:
            entries = pg.list_archive(archive, settings.verify, timeout=60)
            ok = _check(checks, "archive-readable", True, f"pg_restore read {entries} archive entries")
        except pg.PgError as e:
            ok = _check(checks, "archive-readable", False, str(e))

    if ok:
        scratch = f"bdr_verify_{backup_id.lower()}"
        started = time.monotonic()
        try:
            pg.drop_database(settings.verify, scratch)  # left over from an interrupted run
            pg.create_database(settings.verify, scratch)
            pg.restore(archive, settings.verify, scratch, timeout=settings.restore_timeout_seconds)
            result["restore_seconds"] = round(time.monotonic() - started, 2)
            with psycopg.connect(**settings.verify.conninfo(dbname=scratch)) as conn, conn.cursor() as cur:
                revision, counts = pg.snapshot_facts(cur, tuple(expected))
            _check(checks, "restore", True, f"Restored into a disposable database in {result['restore_seconds']} s")
            same_rev = revision == manifest["source"]["schema_revision"]
            ok = _check(checks, "schema-revision", same_rev, f"Schema revision {revision}" + ("" if same_rev else f", expected {manifest['source']['schema_revision']}"))
            diffs = [f"{t}: {counts.get(t)} restored, {n} expected" for t, n in expected.items() if counts.get(t) != n]
            ok = _check(
                checks,
                "record-counts",
                not diffs,
                "Record counts match: " + ", ".join(f"{t} {n}" for t, n in expected.items()) if not diffs else "; ".join(diffs),
            ) and ok
            result["restore_test"] = "passed" if ok else "failed"
        except (pg.PgError, psycopg.Error) as e:
            result["restore_test"] = "failed"
            ok = _check(checks, "restore", False, str(e).strip().splitlines()[0][:500] if str(e).strip() else type(e).__name__)
        finally:
            try:
                pg.drop_database(settings.verify, scratch)
            except psycopg.Error:
                pass  # the verification server is disposable; a leftover scratch DB is dropped on the next run

    failure = next((c["detail"] for c in checks if not c["ok"]), None)
    manifest["verification"] = {
        "state": "passed" if ok else "failed",
        "verified_at": iso(now()),
        "checksum": result["checksum"],
        "restore_test": result["restore_test"],
        "restore_seconds": result["restore_seconds"],
        "checks": checks,
        "failure_reason": failure,
    }
    manifest["status"] = "verified" if ok else "failed"
    manifest["failure_reason"] = None if ok else f"Verification failed: {failure}"
    store.write_manifest(manifest)
    store.log_event(
        severity="info" if ok else "error",
        title="Backup verified" if ok else "Backup failed verification",
        detail=(
            f"Checksum matched and a test restore succeeded in {result['restore_seconds']} s. Usable as a recovery point."
            if ok
            else f"{failure}. This backup will not be offered for recovery."
        ),
        actor=actor,
        backup_id=backup_id,
    )
    return manifest
