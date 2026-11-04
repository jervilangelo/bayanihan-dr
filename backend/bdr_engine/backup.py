"""Creates one consistent backup of the CMS database."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import psycopg

from . import pg
from .config import Settings
from .manifest import backup_id_for, iso, new_manifest, sha256_file, utcnow
from .store import BackupStore


def create_backup(
    settings: Settings,
    store: BackupStore,
    *,
    trigger: str = "manual",
    scheduled_at: datetime | None = None,
    actor: str = "Operator (CLI)",
    now: Callable[[], datetime] = utcnow,
) -> dict[str, Any]:
    """Dumps the source database and writes a manifest. Never raises for database problems: a failed
    backup is recorded (status ``failed``) so missed protection is visible, not silent."""
    started = now()
    backup_id = backup_id_for(started)
    store.create(backup_id)
    manifest = new_manifest(
        backup_id,
        trigger=trigger,
        scheduled_at=scheduled_at or started,
        started_at=started,
        database=settings.source.dbname,
    )
    store.write_manifest(manifest)

    archive = store.archive_path(backup_id)
    partial = archive.with_name(archive.name + ".partial")
    try:
        manifest["source"]["pg_dump_version"] = pg.tool_version("pg_dump")
        with psycopg.connect(**settings.source.conninfo()) as conn:
            # One REPEATABLE READ snapshot is shared with pg_dump, so the record counts in the manifest
            # describe exactly the data inside the archive, even while the CMS keeps writing.
            conn.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
            conn.read_only = True
            with conn.cursor() as cur:
                cur.execute("SELECT pg_export_snapshot(), current_setting('server_version')")
                snapshot, server_version = cur.fetchone()  # type: ignore[misc]
                revision, counts = pg.snapshot_facts(cur, settings.tables)
                if revision is None:
                    raise pg.PgError("the source database has no schema revision (alembic_version); run migrations first")
                pg.dump(settings.source, snapshot=snapshot, out_file=partial, timeout=settings.dump_timeout_seconds)
            conn.rollback()

        sha, size = sha256_file(partial)
        if size == 0:
            raise pg.PgError("pg_dump produced an empty archive")
        partial.replace(archive)
        manifest["source"].update(server_version=server_version, schema_revision=revision)
        manifest["archive"].update(size_bytes=size, sha256=sha)
        manifest["records"] = counts
        manifest["status"] = "unverified"
        manifest["completed_at"] = iso(now())
        store.write_manifest(manifest)
        store.log_event(
            severity="info",
            title="Backup created",
            detail=f"{size:,} bytes, schema {revision}. Waiting for restore verification.",
            actor=actor,
            backup_id=backup_id,
        )
    except (pg.PgError, psycopg.Error, OSError) as e:
        partial.unlink(missing_ok=True)
        reason = str(e).strip().splitlines()[0][:500] if str(e).strip() else type(e).__name__
        manifest.update(status="failed", failure_reason=f"Backup failed: {reason}", completed_at=iso(now()))
        store.write_manifest(manifest)
        store.log_event(severity="error", title="Backup failed", detail=reason, actor=actor, backup_id=backup_id)
    return manifest
