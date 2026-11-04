"""Local retention: decide which backups to delete, with safeguards that keep recovery possible."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .config import RetentionPolicy
from .manifest import parse_iso
from .store import Entry


@dataclass(frozen=True)
class Decision:
    backup_id: str
    keep: bool
    reason: str


def _time(entry: Entry) -> datetime:
    if entry.manifest:
        return parse_iso(entry.manifest["started_at"])
    return datetime.strptime(entry.backup_id, "%Y%m%dT%H%M%S%z")


def plan_retention(entries: list[Entry], now: datetime, policy: RetentionPolicy) -> list[Decision]:
    """Rules, in order:

    1. The newest verified backup is always kept (never delete the last good recovery point).
    2. Everything younger than ``keep_all_hours`` is kept, including failures (diagnostics window).
    3. An in-progress backup is never deleted by retention.
    4. Older verified backups: the newest one per UTC day is kept for ``keep_daily_days`` days.
    5. Everything else is deleted: older failed, unreadable or superseded backups.
    """
    verified = sorted(
        (e for e in entries if e.manifest and e.manifest["status"] == "verified"), key=_time, reverse=True
    )
    newest_verified = verified[0].backup_id if verified else None
    daily_keepers: dict[str, str] = {}
    for e in verified:  # newest first, so the first seen per day wins
        daily_keepers.setdefault(_time(e).strftime("%Y-%m-%d"), e.backup_id)
    daily_ids = set(daily_keepers.values())

    keep_all_after = now - timedelta(hours=policy.keep_all_hours)
    daily_after = now - timedelta(days=policy.keep_daily_days)

    decisions: list[Decision] = []
    for e in sorted(entries, key=_time, reverse=True):
        t = _time(e)
        status = e.manifest["status"] if e.manifest else "unreadable"
        if e.backup_id == newest_verified:
            d = Decision(e.backup_id, True, "newest verified recovery point")
        elif t >= keep_all_after:
            d = Decision(e.backup_id, True, f"within the {policy.keep_all_hours}-hour window")
        elif status == "in-progress":
            d = Decision(e.backup_id, True, "still in progress")
        elif status == "verified" and e.backup_id in daily_ids and t >= daily_after:
            d = Decision(e.backup_id, True, f"daily recovery point (kept {policy.keep_daily_days} days)")
        else:
            d = Decision(e.backup_id, False, f"{status}, older than the retention windows")
        decisions.append(d)
    return decisions
