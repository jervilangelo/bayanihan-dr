from datetime import UTC, datetime

import pytest

from bdr_engine.config import ConfigError, Settings
from bdr_engine.manifest import ManifestError, backup_id_for, dumps, loads, new_manifest, sha256_file
from bdr_engine.store import BackupStore, StoreError

T0 = datetime(2026, 11, 4, 7, 0, 0, tzinfo=UTC)


def manifest(backup_id="20261104T070000Z"):
    return new_manifest(backup_id, trigger="scheduled", scheduled_at=T0, started_at=T0, database="cms")


def test_backup_id_is_utc_start_time():
    assert backup_id_for(T0) == "20261104T070000Z"


def test_manifest_round_trips():
    m = manifest()
    assert loads(dumps(m)) == m
    assert m["status"] == "in-progress"
    assert m["verification"]["state"] == "not-run"


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda m: m.update(backup_id="../etc"), "backup_id"),
        (lambda m: m.update(status="protected"), "status"),
        (lambda m: m.update(format_version=99), "format"),
        (lambda m: m["archive"].update(file="../../x"), "archive file"),
        (lambda m: m.pop("records"), "records"),
    ],
)
def test_invalid_manifests_are_rejected(mutate, message):
    m = manifest()
    mutate(m)
    with pytest.raises(ManifestError, match=message):
        loads(dumps(m))


def test_garbage_manifest_is_rejected():
    with pytest.raises(ManifestError, match="not valid JSON"):
        loads("{not json")


def test_store_refuses_unsafe_ids(store: BackupStore):
    for bad in ("..", "../x", "20261104T070000Z/../..", "latest"):
        with pytest.raises(StoreError):
            store.backup_dir(bad)


def test_store_lists_untrusted_entries(store: BackupStore):
    store.create("20261104T070000Z")
    store.write_manifest(manifest())
    store.create("20261104T080000Z")  # directory without a manifest
    bad = store.create("20261104T090000Z")
    (bad / "manifest.json").write_text("{broken", encoding="utf-8")
    (store.root / "notes").mkdir()  # unrelated folders are ignored

    entries = {e.backup_id: e for e in store.entries()}
    assert list(entries) == ["20261104T090000Z", "20261104T080000Z", "20261104T070000Z"]
    assert entries["20261104T070000Z"].manifest is not None
    assert entries["20261104T080000Z"].error == "manifest.json is missing"
    assert "not valid JSON" in entries["20261104T090000Z"].error


def test_duplicate_backup_id_is_refused(store: BackupStore):
    store.create("20261104T070000Z")
    with pytest.raises(StoreError, match="already exists"):
        store.create("20261104T070000Z")


def test_events_survive_a_torn_last_line(store: BackupStore):
    store.log_event(severity="info", title="One", detail="", actor="t")
    with store.events_path.open("a", encoding="utf-8") as f:
        f.write('{"partial": ')
    assert [e["title"] for e in store.events()] == ["One"]


def test_lock_blocks_a_second_job(store: BackupStore):
    from bdr_engine.store import EngineBusy

    pytest.importorskip("fcntl")
    with store.lock():
        with pytest.raises(EngineBusy):
            with store.lock():
                pass
    with store.lock():  # released after the first job
        pass


def test_sha256_file(tmp_path):
    p = tmp_path / "f"
    p.write_bytes(b"abc")
    assert sha256_file(p) == ("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad", 3)


def test_settings_require_passwords_from_env():
    base = {
        "BDR_SOURCE_HOST": "db",
        "BDR_SOURCE_USER": "cms",
        "BDR_SOURCE_DB": "cms",
        "BDR_VERIFY_HOST": "verify-db",
        "BDR_VERIFY_USER": "postgres",
        "BDR_VERIFY_PASSWORD": "x",
    }
    with pytest.raises(ConfigError, match="BDR_SOURCE_PASSWORD"):
        Settings.from_env(base)
    s = Settings.from_env(base | {"BDR_SOURCE_PASSWORD": "y", "BDR_INTERVAL_MINUTES": "30"})
    assert s.source.dbname == "cms" and s.verify.dbname == "postgres" and s.interval_minutes == 30
    assert s.tables == ("farmers", "inventory_items", "transactions")
    with pytest.raises(ConfigError, match="whole number"):
        Settings.from_env(base | {"BDR_SOURCE_PASSWORD": "y", "BDR_RPO_MINUTES": "soon"})
