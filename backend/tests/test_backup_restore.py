"""Integration tests against a real, disposable PostgreSQL server (the compose ``backup-tests`` service).

These are the Phase 3 exit gate: a repeatable successful restore, and bad backups detected.
"""

from __future__ import annotations

import json
from dataclasses import replace

import psycopg
import pytest

from bdr_engine import pg
from bdr_engine.backup import create_backup
from bdr_engine.jobs import backup_and_verify, prune, write_status
from bdr_engine.manifest import sha256_file
from bdr_engine.store import BackupStore, EngineBusy
from bdr_engine.verify import VerifyError, verify_backup

ACTOR = "pytest"


@pytest.fixture
def engine_store(live_settings) -> BackupStore:
    return BackupStore(live_settings.backup_dir)


def test_backup_then_verify_succeeds_with_exact_counts(live_settings, engine_store):
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    assert m["status"] == "verified", m["failure_reason"]
    assert m["records"] == {"farmers": 5, "inventory_items": 3, "transactions": 7}
    assert m["source"]["schema_revision"] == "0001"
    assert m["source"]["pg_dump_version"].startswith("16")
    v = m["verification"]
    assert v["checksum"] == "match" and v["restore_test"] == "passed" and v["restore_seconds"] >= 0
    assert {c["name"] for c in v["checks"]} >= {"checksum", "archive-readable", "restore", "schema-revision", "record-counts"}
    assert all(c["ok"] for c in v["checks"])
    assert sha256_file(engine_store.archive_path(m["backup_id"]))[0] == m["archive"]["sha256"]
    # the disposable verification database is gone afterwards
    with psycopg.connect(**live_settings.verify.conninfo(), autocommit=True) as conn:
        left = conn.execute("SELECT count(*) FROM pg_database WHERE datname LIKE 'bdr_verify_%'").fetchone()[0]
    assert left == 0


def test_restore_is_repeatable(live_settings, engine_store):
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    for _ in range(3):
        again = verify_backup(live_settings, engine_store, m["backup_id"], actor=ACTOR)
        assert again["status"] == "verified"


def test_backup_reflects_new_data(live_settings, engine_store, source_db):
    first = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    with psycopg.connect(**source_db.conninfo()) as conn:
        conn.execute("INSERT INTO farmers (name) VALUES ('Late joiner')")
    import time

    time.sleep(1.1)  # backup IDs have one-second resolution
    second = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    assert first["records"]["farmers"] == 5 and second["records"]["farmers"] == 6
    assert second["status"] == "verified"


def test_corrupted_archive_is_detected_by_checksum(live_settings, engine_store):
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    archive = engine_store.archive_path(m["backup_id"])
    data = bytearray(archive.read_bytes())
    data[len(data) // 2] ^= 0xFF
    archive.write_bytes(bytes(data))

    m = verify_backup(live_settings, engine_store, m["backup_id"], actor=ACTOR)
    assert m["status"] == "failed"
    assert m["verification"]["checksum"] == "mismatch"
    assert m["verification"]["restore_test"] == "not-run"
    assert "SHA-256 does not match" in m["failure_reason"]


def test_truncated_archive_with_matching_checksum_fails_the_restore(live_settings, engine_store):
    """A checksum alone proves nothing: an archive that was truncated *before* hashing must still fail."""
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    archive = engine_store.archive_path(m["backup_id"])
    archive.write_bytes(archive.read_bytes()[: archive.stat().st_size // 2])
    sha, size = sha256_file(archive)
    m["archive"].update(sha256=sha, size_bytes=size)
    engine_store.write_manifest(m)

    m = verify_backup(live_settings, engine_store, m["backup_id"], actor=ACTOR)
    assert m["status"] == "failed"
    assert m["verification"]["checksum"] == "match"
    assert m["failure_reason"].startswith("Verification failed: pg_restore failed")


def test_record_count_mismatch_is_detected(live_settings, engine_store):
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    m["records"]["transactions"] = 999
    engine_store.write_manifest(m)
    m = verify_backup(live_settings, engine_store, m["backup_id"], actor=ACTOR)
    assert m["status"] == "failed" and m["verification"]["restore_test"] == "failed"
    assert "transactions: 7 restored, 999 expected" in m["failure_reason"]


def test_missing_manifest_is_rejected_and_reported(live_settings, engine_store):
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    engine_store.manifest_path(m["backup_id"]).unlink()
    with pytest.raises(VerifyError, match="manifest.json is missing"):
        verify_backup(live_settings, engine_store, m["backup_id"], actor=ACTOR)
    status = write_status(live_settings, engine_store)
    view = next(b for b in status["backups"] if b["id"] == m["backup_id"])
    assert view["status"] == "failed" and view["failureReason"].startswith("Not trusted")


def test_unreachable_database_records_a_failed_backup(live_settings, engine_store):
    bad = replace(live_settings, source=replace(live_settings.source, password="wrong-password"))
    m = create_backup(bad, engine_store, trigger="manual", actor=ACTOR)
    assert m["status"] == "failed" and m["failure_reason"].startswith("Backup failed:")
    assert not engine_store.archive_path(m["backup_id"]).exists()
    assert not any(engine_store.backup_dir(m["backup_id"]).glob("*.partial"))
    with pytest.raises(VerifyError, match="no archive"):
        verify_backup(live_settings, engine_store, m["backup_id"], actor=ACTOR)
    assert engine_store.events()[-1]["title"] == "Backup failed"


def test_unmigrated_database_fails_closed(live_settings, engine_store, source_db):
    with psycopg.connect(**source_db.conninfo()) as conn:
        conn.execute("DROP TABLE alembic_version")
    m = create_backup(live_settings, engine_store, trigger="manual", actor=ACTOR)
    assert m["status"] == "failed" and "no schema revision" in m["failure_reason"]


def test_concurrent_jobs_are_refused(live_settings, engine_store):
    with engine_store.lock():
        with pytest.raises(EngineBusy):
            backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)


def test_prune_keeps_the_only_verified_backup(live_settings, engine_store):
    m = backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    from datetime import timedelta

    from bdr_engine.manifest import parse_iso

    far_future = parse_iso(m["started_at"]) + timedelta(days=60)
    decisions = prune(live_settings, engine_store, apply=True, actor=ACTOR, now=far_future)
    assert [d.keep for d in decisions] == [True]
    assert engine_store.archive_path(m["backup_id"]).exists()


def test_status_file_is_written_for_the_dashboard(live_settings, engine_store):
    backup_and_verify(live_settings, engine_store, trigger="manual", actor=ACTOR)
    write_status(live_settings, engine_store)
    status = json.loads(engine_store.status_path.read_text(encoding="utf-8"))
    assert status["primary"]["status"] == "online" and status["primary"]["schemaRevision"] == "0001"
    assert status["backups"][0]["status"] == "verified"
    assert {a["title"] for a in status["activity"]} >= {"Backup created", "Backup verified"}
