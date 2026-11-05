import base64
import hashlib
from datetime import UTC, datetime

import pytest

from bdr_engine.manifest import new_manifest, sha256_file
from bdr_engine.offsite import OffsiteError, object_keys, upload_backup
from bdr_engine.store import BackupStore

T0 = datetime(2026, 11, 5, 6, 0, tzinfo=UTC)
BID = "20261105T060000Z"


class FakeS3:
    """Records put_object calls and, like S3, checks the SHA-256 it was given."""

    def __init__(self, fail: Exception | None = None):
        self.calls: list[dict] = []
        self.fail = fail

    def put_object(self, **kw):
        if self.fail:
            raise self.fail
        body = kw["Body"].read() if hasattr(kw["Body"], "read") else kw["Body"]
        if base64.b64encode(hashlib.sha256(body).digest()).decode() != kw["ChecksumSHA256"]:
            raise RuntimeError("BadDigest: the SHA-256 you specified did not match what we received")
        self.calls.append({**kw, "Body": body})
        return {"VersionId": f"v{len(self.calls)}"}


def make_backup(store: BackupStore, status: str = "verified") -> None:
    store.create(BID)
    store.archive_path(BID).write_bytes(b"PGDMP fake archive bytes" * 100)
    sha, size = sha256_file(store.archive_path(BID))
    m = new_manifest(BID, trigger="scheduled", scheduled_at=T0, started_at=T0, database="cms")
    m["status"] = status
    m["archive"].update(sha256=sha, size_bytes=size)
    m["source"]["schema_revision"] = "0001"
    store.write_manifest(m)


def test_uploads_archive_then_manifest_and_records_it(store):
    make_backup(store)
    s3 = FakeS3()
    m = upload_backup(store, BID, bucket="b", prefix="backups/", client=s3)
    assert [c["Key"] for c in s3.calls] == list(object_keys("backups/", BID))
    assert s3.calls[0]["Metadata"]["sha256"] == m["archive"]["sha256"]
    assert m["offsite"] == "stored" and m["offsite_detail"]["version_id"] == "v1"
    assert store.read_manifest(BID)["offsite"] == "stored"
    assert store.events()[-1]["title"] == "Backup copied off-site"
    # already stored: no second upload
    upload_backup(store, BID, bucket="b", prefix="backups/", client=s3)
    assert len(s3.calls) == 2


@pytest.mark.parametrize("status", ["unverified", "failed", "in-progress"])
def test_refuses_anything_not_verified(store, status):
    make_backup(store, status)
    with pytest.raises(OffsiteError, match="only verified"):
        upload_backup(store, BID, bucket="b", prefix="backups/", client=FakeS3())


def test_refuses_an_archive_changed_after_verification(store):
    make_backup(store)
    store.archive_path(BID).write_bytes(b"tampered")
    s3 = FakeS3()
    with pytest.raises(OffsiteError, match="no longer matches"):
        upload_backup(store, BID, bucket="b", prefix="backups/", client=s3)
    assert s3.calls == []


def test_failed_upload_is_recorded_not_marked_stored(store):
    make_backup(store)
    with pytest.raises(OffsiteError, match="AccessDenied"):
        upload_backup(store, BID, bucket="b", prefix="backups/", client=FakeS3(fail=RuntimeError("AccessDenied: nope")))
    m = store.read_manifest(BID)
    assert m["offsite"] == "rejected" and "AccessDenied" in m["offsite_detail"]["error"]
    assert store.events()[-1]["severity"] == "error"
