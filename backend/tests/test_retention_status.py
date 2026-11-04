from datetime import UTC, datetime, timedelta

from bdr_engine.config import RetentionPolicy
from bdr_engine.manifest import backup_id_for, new_manifest
from bdr_engine.retention import plan_retention
from bdr_engine.scheduler import next_slot
from bdr_engine.status import build_status, missed_slots
from bdr_engine.store import Entry

from .conftest import make_settings

NOW = datetime(2026, 11, 10, 12, 30, tzinfo=UTC)
POLICY = RetentionPolicy(keep_all_hours=24, keep_daily_days=7)


def entry(hours_ago: float, status: str = "verified", trigger: str = "scheduled", archive: bool = True) -> Entry:
    t = NOW - timedelta(hours=hours_ago)
    bid = backup_id_for(t)
    m = new_manifest(bid, trigger=trigger, scheduled_at=t.replace(minute=0, second=0), started_at=t, database="cms")
    m["status"] = status
    if status != "in-progress":
        m["completed_at"] = m["started_at"]
        m["archive"].update(size_bytes=1000, sha256="ab" * 32)
        m["records"] = {"farmers": 5, "inventory_items": 3}
    if status == "verified":
        m["verification"].update(state="passed", checksum="match", restore_test="passed", restore_seconds=1.2)
    if status == "failed":
        m["failure_reason"] = "Verification failed: SHA-256 does not match the manifest"
    return Entry(bid, m, None, archive)


def keep_map(entries):
    return {d.backup_id: d.keep for d in plan_retention(entries, NOW, POLICY)}


# ---- retention ----
def test_recent_backups_are_all_kept_including_failures():
    es = [entry(1), entry(2, "failed"), entry(23, "verified")]
    assert all(keep_map(es).values())


def test_old_failures_and_superseded_backups_are_deleted_daily_keepers_kept():
    newest = entry(1)
    old_fail = entry(30, "failed")
    day_a_new, day_a_old = entry(30.5), entry(31.5)  # both on 9 Nov UTC: the newest of the day wins
    too_old = entry(24 * 9)
    keep = keep_map([newest, old_fail, day_a_new, day_a_old, too_old])
    assert keep[newest.backup_id]
    assert not keep[old_fail.backup_id]
    assert keep[day_a_new.backup_id] and not keep[day_a_old.backup_id]
    assert not keep[too_old.backup_id]


def test_newest_verified_backup_is_never_deleted_even_if_ancient():
    only_good = entry(24 * 30)
    keep = keep_map([entry(48, "failed"), only_good])
    assert keep[only_good.backup_id]


def test_in_progress_is_never_deleted_and_unreadable_old_entries_are():
    stuck = entry(48, "in-progress")
    unreadable = Entry(backup_id_for(NOW - timedelta(hours=50)), None, "manifest.json is missing", True)
    keep = keep_map([entry(1), stuck, unreadable])
    assert keep[stuck.backup_id] and not keep[unreadable.backup_id]


# ---- schedule ----
def test_next_slot_is_strictly_after_now():
    assert next_slot(datetime(2026, 11, 4, 7, 0, tzinfo=UTC), 60) == datetime(2026, 11, 4, 8, 0, tzinfo=UTC)
    assert next_slot(datetime(2026, 11, 4, 7, 59, 59, tzinfo=UTC), 60) == datetime(2026, 11, 4, 8, 0, tzinfo=UTC)
    assert next_slot(datetime(2026, 11, 4, 7, 10, tzinfo=UTC), 15) == datetime(2026, 11, 4, 7, 15, tzinfo=UTC)


def test_missed_slots_start_at_first_scheduled_backup_and_ignore_manual_runs():
    es = [entry(4.5), entry(2.5), entry(1.2, trigger="manual")]  # slots 08:00 and 10:00 ran
    missed = missed_slots(es, NOW, 60)
    # 09:00 and 11:00 have no scheduled attempt; 12:00 is past its 15-minute grace at 12:30
    assert [m.hour for m in missed] == [9, 11, 12]


def test_no_schedule_means_no_missed_slots():
    assert missed_slots([entry(5, trigger="manual")], NOW, 60) == []


# ---- status.json ----
def test_status_maps_manifests_to_dashboard_shapes(tmp_path):
    settings = make_settings(tmp_path)
    es = [
        entry(0.4),
        entry(1.4, "failed"),
        entry(2.4, "in-progress"),  # older than dump timeout + 5 min: reported as failed
        entry(3.4, archive=False),  # verified but archive deleted: not a recovery point
        Entry("20261110T080000Z", None, "manifest.json is missing", True),
    ]
    status = build_status(settings, es, [], NOW, {"status": "online"})
    by_id = {b["id"]: b for b in status["backups"]}
    assert status["schemaVersion"] == 1 and status["mode"] == "operational"
    good = by_id[es[0].backup_id]
    assert good["status"] == "verified" and good["records"] == {"farmers": 5, "inventoryItems": 3}
    assert good["checksum"] == "match" and good["restoreTest"] == "passed" and good["offsite"] == "not-stored"
    assert by_id[es[1].backup_id]["status"] == "failed"
    fresh = build_status(settings, [entry(0.01, "in-progress"), entry(0.02, "unverified")], [], NOW, {})
    assert [b["status"] for b in fresh["backups"]] == ["pending", "pending"]
    assert "did not finish" in by_id[es[2].backup_id]["failureReason"]
    assert "removed" in by_id[es[3].backup_id]["failureReason"]
    assert by_id["20261110T080000Z"]["failureReason"].startswith("Not trusted")
    assert [b["scheduledAt"] for b in status["backups"]] == sorted((b["scheduledAt"] for b in status["backups"]), reverse=True)
    assert all(a["simulated"] is False for a in status["activity"])
