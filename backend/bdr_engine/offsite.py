"""Off-site copies: upload verified backups to the encrypted S3 bucket (Phase 5).

Only ``verified`` backups are uploaded: an unverified copy off-site would only look like protection.
Every object is sent with its SHA-256 checksum, which S3 checks on arrival and rejects on mismatch.
The engine runs with the upload-only ``backup-writer`` role: it can add objects but not read or delete them.
"""

from __future__ import annotations

import base64
import hashlib
from collections.abc import Callable
from datetime import datetime
from typing import Any, Protocol

from .manifest import ARCHIVE_NAME, MANIFEST_NAME, dumps, iso, sha256_file, utcnow
from .store import BackupStore


class OffsiteError(RuntimeError):
    pass


class S3Client(Protocol):  # the subset of boto3's S3 client used here
    def put_object(self, **kwargs: Any) -> dict[str, Any]: ...


def default_client(region: str) -> S3Client:
    import boto3  # imported lazily: only needed when off-site upload is configured

    return boto3.client("s3", region_name=region)


def _b64(hex_digest: str) -> str:
    return base64.b64encode(bytes.fromhex(hex_digest)).decode()


def object_keys(prefix: str, backup_id: str) -> tuple[str, str]:
    return f"{prefix}{backup_id}/{ARCHIVE_NAME}", f"{prefix}{backup_id}/{MANIFEST_NAME}"


def upload_backup(
    store: BackupStore,
    backup_id: str,
    *,
    bucket: str,
    prefix: str,
    client: S3Client,
    actor: str = "Operator (CLI)",
    now: Callable[[], datetime] = utcnow,
) -> dict[str, Any]:
    manifest = store.read_manifest(backup_id)
    if manifest["status"] != "verified":
        raise OffsiteError(f"backup {backup_id} is {manifest['status']}; only verified backups are copied off-site")
    if manifest.get("offsite") == "stored":
        return manifest

    archive = store.archive_path(backup_id)
    sha, size = sha256_file(archive)
    if sha != manifest["archive"]["sha256"] or size != manifest["archive"]["size_bytes"]:
        # The local copy changed after verification: refuse, and let the next verify mark it failed.
        raise OffsiteError(f"backup {backup_id} no longer matches its verified checksum; not uploading")

    archive_key, manifest_key = object_keys(prefix, backup_id)
    try:
        with archive.open("rb") as body:
            result = client.put_object(
                Bucket=bucket,
                Key=archive_key,
                Body=body,
                ChecksumSHA256=_b64(sha),  # S3 recomputes it and rejects the upload on mismatch
                ContentType="application/octet-stream",
                Metadata={"backup-id": backup_id, "sha256": sha, "schema-revision": manifest["source"]["schema_revision"]},
            )
        text = dumps(manifest).encode()
        client.put_object(
            Bucket=bucket,
            Key=manifest_key,
            Body=text,
            ChecksumSHA256=_b64(hashlib.sha256(text).hexdigest()),
            ContentType="application/json",
        )
    except Exception as e:  # botocore raises many types; record the reason, never mark it stored
        reason = str(e).strip().splitlines()[0][:300] if str(e).strip() else type(e).__name__
        manifest["offsite"] = "rejected"
        manifest["offsite_detail"] = {"bucket": bucket, "key": archive_key, "error": reason, "attempted_at": iso(now())}
        store.write_manifest(manifest)
        store.log_event(severity="error", title="Off-site upload failed", detail=reason, actor=actor, backup_id=backup_id)
        raise OffsiteError(f"upload of {backup_id} failed: {reason}") from e

    manifest["offsite"] = "stored"
    manifest["offsite_detail"] = {
        "bucket": bucket,
        "key": archive_key,
        "version_id": result.get("VersionId"),
        "uploaded_at": iso(now()),
    }
    store.write_manifest(manifest)
    store.log_event(
        severity="info",
        title="Backup copied off-site",
        detail=f"Encrypted copy stored in S3 ({size:,} bytes); SHA-256 checked by S3 on arrival.",
        actor=actor,
        backup_id=backup_id,
    )
    return manifest
