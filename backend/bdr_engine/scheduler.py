"""Long-running scheduler: one backup per slot (hourly by default), then verify, prune and report."""

from __future__ import annotations

import logging
import signal
import threading
from datetime import datetime, timedelta

from .config import Settings
from .jobs import backup_and_verify, prune, write_status
from .manifest import iso, utcnow
from .status import slot_start
from .store import BackupStore, EngineBusy

log = logging.getLogger("bdr_engine.scheduler")
STATUS_REFRESH = timedelta(minutes=1)
ACTOR = "Backup scheduler"


def next_slot(now: datetime, interval_minutes: int) -> datetime:
    """The next slot boundary strictly after ``now``."""
    return slot_start(now, interval_minutes) + timedelta(minutes=interval_minutes)


def run_slot(settings: Settings, store: BackupStore, slot: datetime) -> None:
    try:
        manifest = backup_and_verify(settings, store, trigger="scheduled", scheduled_at=slot, actor=ACTOR)
        log.info("slot %s: backup %s is %s", iso(slot), manifest["backup_id"], manifest["status"])
        prune(settings, store, apply=True, actor=ACTOR)
    except EngineBusy:
        store.log_event(severity="warning", title="Scheduled backup skipped", detail="Another engine job was still running.", actor=ACTOR)
        log.warning("slot %s skipped: another job holds the lock", iso(slot))
    except Exception:  # keep the scheduler alive; the failure is in the log and the event history
        log.exception("slot %s failed unexpectedly", iso(slot))
        store.log_event(severity="error", title="Scheduler error", detail="Unexpected engine error; see the engine log.", actor=ACTOR)


def run_forever(settings: Settings, store: BackupStore, *, run_now: bool = False) -> None:
    stop = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stop.set())

    log.info("scheduler started: every %d min, backups in %s", settings.interval_minutes, store.root)
    store.log_event(severity="info", title="Backup scheduler started", detail=f"Every {settings.interval_minutes} minutes.", actor=ACTOR)
    if run_now:
        run_slot(settings, store, slot_start(utcnow(), settings.interval_minutes))
    upcoming = next_slot(utcnow(), settings.interval_minutes)
    while not stop.is_set():
        try:
            write_status(settings, store)
        except Exception:
            log.exception("could not write status.json")
        wait = min((upcoming - utcnow()).total_seconds(), STATUS_REFRESH.total_seconds())
        if wait > 0 and stop.wait(wait):
            break
        if utcnow() >= upcoming:
            run_slot(settings, store, upcoming)
            upcoming = next_slot(utcnow(), settings.interval_minutes)
    store.log_event(severity="info", title="Backup scheduler stopped", detail="Received a stop signal.", actor=ACTOR)
    write_status(settings, store)
    log.info("scheduler stopped")
