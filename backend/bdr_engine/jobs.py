"""Job entry points shared by the CLI and the scheduler. Every job that changes the store holds the lock."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime
from typing import Any

from .backup import create_backup
from .config import Settings
from .manifest import utcnow
from .retention import Decision, plan_retention
from .status import build_status, probe_primary
from .store import BackupStore, write_atomic
from .verify import verify_backup


def backup_and_verify(
    settings: Settings,
    store: BackupStore,
    *,
    trigger: str,
    scheduled_at: datetime | None = None,
    actor: str,
) -> dict[str, Any]:
    with store.lock():
        manifest = create_backup(settings, store, trigger=trigger, scheduled_at=scheduled_at, actor=actor)
        if manifest["status"] == "unverified":
            manifest = verify_backup(settings, store, manifest["backup_id"], actor=actor)
        return manifest


def prune(settings: Settings, store: BackupStore, *, apply: bool, actor: str, now: datetime | None = None) -> list[Decision]:
    with store.lock():
        decisions = plan_retention(store.entries(), now or utcnow(), settings.retention)
        if apply:
            for d in decisions:
                if not d.keep:
                    store.delete(d.backup_id)
                    store.log_event(severity="info", title="Backup deleted by retention", detail=d.reason, actor=actor, backup_id=d.backup_id)
        return decisions


def write_status(settings: Settings, store: BackupStore, now: Callable[[], datetime] = utcnow) -> dict[str, Any]:
    t = now()
    status = build_status(settings, store.entries(), store.events(), t, probe_primary(settings, t))
    store.root.mkdir(parents=True, exist_ok=True)
    write_atomic(store.status_path, json.dumps(status, indent=2) + "\n")
    return status
