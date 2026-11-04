"""Backup manifests: the record of what a backup contains and whether it has been proven restorable."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__

FORMAT_VERSION = 1
ARCHIVE_NAME = "cms.dump"
MANIFEST_NAME = "manifest.json"

# A backup ID is the UTC start time, e.g. 20261104T070000Z. Strict so it is always safe as a path segment.
BACKUP_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")

STATUSES = ("in-progress", "unverified", "verified", "failed")


class ManifestError(ValueError):
    pass


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def backup_id_for(dt: datetime) -> str:
    return dt.astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


def is_backup_id(value: str) -> bool:
    return bool(BACKUP_ID_RE.match(value))


def sha256_file(path: Path, chunk: int = 1 << 20) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as f:
        while block := f.read(chunk):
            digest.update(block)
            size += len(block)
    return digest.hexdigest(), size


def new_manifest(backup_id: str, *, trigger: str, scheduled_at: datetime, started_at: datetime, database: str) -> dict[str, Any]:
    if not is_backup_id(backup_id):
        raise ManifestError(f"invalid backup id {backup_id!r}")
    if trigger not in ("scheduled", "manual"):
        raise ManifestError(f"invalid trigger {trigger!r}")
    return {
        "format_version": FORMAT_VERSION,
        "backup_id": backup_id,
        "trigger": trigger,
        "scheduled_at": iso(scheduled_at),
        "started_at": iso(started_at),
        "completed_at": None,
        "status": "in-progress",
        "failure_reason": None,
        "engine_version": __version__,
        "source": {"database": database, "server_version": None, "pg_dump_version": None, "schema_revision": None},
        "archive": {"file": ARCHIVE_NAME, "format": "pg_dump-custom", "size_bytes": None, "sha256": None},
        "records": {},
        "verification": {
            "state": "not-run",
            "verified_at": None,
            "checksum": "not-run",
            "restore_test": "not-run",
            "restore_seconds": None,
            "checks": [],
            "failure_reason": None,
        },
        "offsite": "not-stored",
    }


def validate(manifest: Any) -> dict[str, Any]:
    """Structural check of a manifest read from disk. Raises ManifestError on anything unexpected."""
    if not isinstance(manifest, dict):
        raise ManifestError("manifest is not a JSON object")
    if manifest.get("format_version") != FORMAT_VERSION:
        raise ManifestError(f"unsupported manifest format {manifest.get('format_version')!r}")
    if not isinstance(manifest.get("backup_id"), str) or not is_backup_id(manifest["backup_id"]):
        raise ManifestError("manifest has an invalid backup_id")
    if manifest.get("status") not in STATUSES:
        raise ManifestError(f"manifest has an invalid status {manifest.get('status')!r}")
    for key in ("source", "archive", "records", "verification"):
        if not isinstance(manifest.get(key), dict):
            raise ManifestError(f"manifest field {key!r} is missing or malformed")
    if manifest["archive"].get("file") != ARCHIVE_NAME:
        raise ManifestError("manifest names an unexpected archive file")
    for key in ("scheduled_at", "started_at"):
        try:
            parse_iso(manifest[key])
        except (KeyError, TypeError, ValueError) as e:
            raise ManifestError(f"manifest field {key!r} is not a timestamp") from e
    return manifest


def dumps(manifest: dict[str, Any]) -> str:
    return json.dumps(manifest, indent=2, sort_keys=True) + "\n"


def loads(text: str) -> dict[str, Any]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ManifestError(f"manifest is not valid JSON: {e.msg}") from e
    return validate(data)
