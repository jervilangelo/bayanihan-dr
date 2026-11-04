"""On-disk backup store.

Layout under the backup root::

    <root>/<backup-id>/cms.dump        pg_dump custom-format archive
    <root>/<backup-id>/manifest.json   metadata, checksum, verification result
    <root>/events.jsonl                append-only engine event log
    <root>/status.json                 dashboard status snapshot
    <root>/.engine.lock                held while a job runs (prevents concurrent jobs)
"""

from __future__ import annotations

import json
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .manifest import ARCHIVE_NAME, MANIFEST_NAME, ManifestError, dumps, is_backup_id, iso, loads, utcnow

try:  # The engine runs on Linux (container or EC2). fcntl is absent on Windows, where only pure logic is used.
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]


class StoreError(RuntimeError):
    pass


class EngineBusy(StoreError):
    """Another backup, verification or prune job holds the lock."""


@dataclass
class Entry:
    """One backup directory. ``manifest`` is None when it is missing or unreadable (``error`` says why)."""

    backup_id: str
    manifest: dict[str, Any] | None
    error: str | None
    archive_present: bool


def write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class BackupStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    # ---- paths (every path is derived from a validated ID, never from raw input) ----
    def backup_dir(self, backup_id: str) -> Path:
        if not is_backup_id(backup_id):
            raise StoreError(f"invalid backup id {backup_id!r}")
        path = (self.root / backup_id).resolve()
        if path.parent != self.root.resolve():
            raise StoreError("backup path escapes the backup root")
        return path

    def archive_path(self, backup_id: str) -> Path:
        return self.backup_dir(backup_id) / ARCHIVE_NAME

    def manifest_path(self, backup_id: str) -> Path:
        return self.backup_dir(backup_id) / MANIFEST_NAME

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"

    @property
    def status_path(self) -> Path:
        return self.root / "status.json"

    # ---- backups ----
    def create(self, backup_id: str) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.backup_dir(backup_id)
        try:
            path.mkdir()
        except FileExistsError as e:
            raise StoreError(f"backup {backup_id} already exists") from e
        return path

    def write_manifest(self, manifest: dict[str, Any]) -> None:
        write_atomic(self.manifest_path(manifest["backup_id"]), dumps(manifest))

    def read_manifest(self, backup_id: str) -> dict[str, Any]:
        path = self.manifest_path(backup_id)
        if not path.exists():
            raise ManifestError("manifest.json is missing")
        manifest = loads(path.read_text(encoding="utf-8"))
        if manifest["backup_id"] != backup_id:
            raise ManifestError("manifest belongs to a different backup")
        return manifest

    def entries(self) -> list[Entry]:
        """All backup directories, newest first. Unrelated files and folders are ignored."""
        if not self.root.exists():
            return []
        found: list[Entry] = []
        for child in self.root.iterdir():
            if not child.is_dir() or not is_backup_id(child.name):
                continue
            try:
                manifest, error = self.read_manifest(child.name), None
            except ManifestError as e:
                manifest, error = None, str(e)
            found.append(Entry(child.name, manifest, error, (child / ARCHIVE_NAME).exists()))
        return sorted(found, key=lambda e: e.backup_id, reverse=True)

    def delete(self, backup_id: str) -> None:
        shutil.rmtree(self.backup_dir(backup_id))

    # ---- events ----
    def log_event(self, *, severity: str, title: str, detail: str, actor: str, backup_id: str | None = None) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        now = utcnow()
        event = {
            "id": f"ev-{now.strftime('%Y%m%dT%H%M%S%fZ')}",
            "at": iso(now),
            "severity": severity,
            "title": title,
            "detail": detail,
            "actor": actor,
            "backup_id": backup_id,
        }
        with self.events_path.open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(event, sort_keys=True) + "\n")

    def events(self, limit: int = 500) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self.events_path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # a torn final line after a crash must not hide the rest of the log
        return out

    # ---- lock ----
    @contextmanager
    def lock(self) -> Iterator[None]:
        """Exclusive, non-blocking job lock. Released by the OS if the process dies."""
        if fcntl is None:  # pragma: no cover
            raise StoreError("job locking needs a POSIX system; run the engine in its container")
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".engine.lock").open("a+") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as e:
                raise EngineBusy("another engine job is already running") from e
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
