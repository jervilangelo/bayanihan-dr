"""Builds status.json: the engine's read-only report for the dashboard's local operations mode.

The field names follow the dashboard's TypeScript contracts (frontend/src/data/types.ts), schema v1.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from .config import Settings
from .manifest import iso, parse_iso
from .store import Entry

STATUS_SCHEMA = 1
WINDOW_HOURS = 72
MISSED_GRACE = timedelta(minutes=15)


def _camel(name: str) -> str:
    head, *rest = name.split("_")
    return head + "".join(p.title() for p in rest)


def slot_start(dt: datetime, interval_minutes: int) -> datetime:
    step = interval_minutes * 60
    return datetime.fromtimestamp(int(dt.timestamp()) // step * step, tz=dt.tzinfo)


def backup_view(entry: Entry, now: datetime, stale_after: timedelta) -> dict[str, Any]:
    """One backup in the dashboard's ``Backup`` shape."""
    m = entry.manifest
    if m is None:
        when = iso(datetime.strptime(entry.backup_id, "%Y%m%dT%H%M%S%z"))
        return {
            "id": entry.backup_id,
            "scheduledAt": when,
            "completedAt": None,
            "status": "failed",
            "sizeBytes": None,
            "sha256": None,
            "checksum": "not-run",
            "restoreTest": "not-run",
            "offsite": "not-stored",
            "failureReason": f"Not trusted: {entry.error}.",
            "schemaRevision": "unknown",
            "trigger": "unknown",
        }
    v = m["verification"]
    status = m["status"]
    reason = m["failure_reason"]
    if status == "in-progress" and now - parse_iso(m["started_at"]) > stale_after:
        status, reason = "failed", "Backup did not finish: the engine stopped while it was running."
    elif status == "verified" and not entry.archive_present:
        status, reason = "failed", "The archive file has been removed since it was verified."
    elif status in ("in-progress", "unverified"):
        status = "pending"  # exists, but not proven restorable: never offered as a recovery point
    view: dict[str, Any] = {
        "id": m["backup_id"],
        "scheduledAt": m["scheduled_at"],
        "completedAt": m["completed_at"],
        "status": status,
        "sizeBytes": m["archive"]["size_bytes"],
        "sha256": m["archive"]["sha256"],
        "checksum": v["checksum"],
        "restoreTest": v["restore_test"],
        "offsite": m["offsite"],
        "schemaRevision": m["source"]["schema_revision"] or "unknown",
        "trigger": m["trigger"],
        "verifiedAt": v["verified_at"],
        "restoreSeconds": v["restore_seconds"],
        "checks": v["checks"],
    }
    if m["records"]:
        view["records"] = {_camel(k): n for k, n in m["records"].items()}
    if reason:
        view["failureReason"] = reason
    return view


def missed_slots(entries: list[Entry], now: datetime, interval_minutes: int) -> list[datetime]:
    """Schedule slots with no attempt at all, from the first scheduled backup (within the window) onward.

    Manual backups do not fill a slot: they prove the engine works, not that the schedule is running.
    """
    scheduled = {
        slot_start(parse_iso(e.manifest["scheduled_at"]), interval_minutes)
        for e in entries
        if e.manifest and e.manifest["trigger"] == "scheduled"
    }
    if not scheduled:
        return []
    step = timedelta(minutes=interval_minutes)
    slot = max(min(scheduled), slot_start(now - timedelta(hours=WINDOW_HOURS), interval_minutes))
    out: list[datetime] = []
    while slot + MISSED_GRACE < now:
        if slot not in scheduled:
            out.append(slot)
        slot += step
    return out


def build_status(
    settings: Settings,
    entries: list[Entry],
    events: list[dict[str, Any]],
    now: datetime,
    primary: dict[str, Any],
) -> dict[str, Any]:
    stale_after = timedelta(seconds=settings.dump_timeout_seconds + 300)
    backups = [backup_view(e, now, stale_after) for e in entries]
    activity = [
        {
            "id": ev["id"],
            "at": ev["at"],
            "category": "backup",
            "severity": ev["severity"],
            "title": ev["title"],
            "detail": ev["detail"],
            "actor": ev["actor"],
            **({"backupId": ev["backup_id"]} if ev.get("backup_id") else {}),
            "simulated": False,
        }
        for ev in events
    ]
    for slot in missed_slots(entries, now, settings.interval_minutes):
        slot_id = slot.strftime("%Y%m%dT%H%M%SZ")
        backups.append(
            {
                "id": f"missed-{slot_id}",
                "scheduledAt": iso(slot),
                "completedAt": None,
                "status": "missed",
                "sizeBytes": None,
                "sha256": None,
                "checksum": "not-run",
                "restoreTest": "not-run",
                "offsite": "not-stored",
                "failureReason": "No backup ran in this slot. The scheduler or the host was not running.",
                "schemaRevision": "unknown",
                "trigger": "scheduled",
            }
        )
        activity.append(
            {
                "id": f"ev-missed-{slot_id}",
                "at": iso(slot + MISSED_GRACE),
                "category": "backup",
                "severity": "warning",
                "title": "Scheduled backup missed",
                "detail": f"No backup started for the {iso(slot)} slot.",
                "actor": "Backup engine",
                "simulated": False,
            }
        )
    backups.sort(key=lambda b: b["scheduledAt"], reverse=True)
    activity.sort(key=lambda a: a["at"], reverse=True)
    r = settings.retention
    return {
        "schemaVersion": STATUS_SCHEMA,
        "generatedAt": iso(now),
        "mode": "operational",
        "primary": primary,
        "targets": {"rtoMinutes": settings.rto_minutes, "rpoMinutes": settings.rpo_minutes},
        "schedule": {
            "intervalMinutes": settings.interval_minutes,
            "description": f"Every {settings.interval_minutes} minutes, on the clock (UTC)"
            if settings.interval_minutes != 60
            else "Every hour, on the hour",
        },
        "retention": {
            "description": f"All backups for {r.keep_all_hours} hours, then one verified backup per day for "
            f"{r.keep_daily_days} days. The newest verified backup is never deleted.",
        },
        "restoreTest": "Every backup is restored into a disposable PostgreSQL database and its record counts are checked.",
        "database": settings.source.dbname,
        "backups": backups,
        "activity": activity[:300],
    }


def probe_primary(settings: Settings, now: datetime) -> dict[str, Any]:
    """Is the CMS database reachable right now, and at which schema revision?"""
    import psycopg

    from . import pg

    info: dict[str, Any] = {
        "name": settings.primary_name,
        "location": settings.primary_location,
        "status": "unreachable",
        "checkedAt": iso(now),
        "schemaRevision": "unknown",
    }
    try:
        with psycopg.connect(**settings.source.conninfo(connect_timeout=3)) as conn, conn.cursor() as cur:
            revision, _ = pg.snapshot_facts(cur, ())
        info.update(status="online", schemaRevision=revision or "unknown")
    except psycopg.Error:
        pass
    return info
