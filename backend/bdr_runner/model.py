"""Jobs, their states, and the on-disk job store with an append-only audit log."""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BACKUP_ID_RE = re.compile(r"^\d{8}T\d{6}Z$")
JOB_ID_RE = re.compile(r"^job-\d{8}T\d{6}Z-[a-f0-9]{6}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")

JOB_TYPES = ("recovery-drill", "teardown")
ACTIVE = ("preparing", "awaiting-approval", "applying", "restoring")
TERMINAL = ("succeeded", "failed", "cancelled")

# Steps shown to the operator, in order. Host steps mirror the events the recovery host reports.
DRILL_STEPS = [
    ("preflight", "Preflight checks"),
    ("plan", "Terraform plan and safety check"),
    ("approval", "Operator approval"),
    ("provision", "Provision recovery environment"),
    ("install", "Install Docker and Git"),
    ("fetch-app", "Fetch CMS source"),
    ("download", "Download backup from S3"),
    ("verify-checksum", "Verify backup checksum"),
    ("start-db", "Start PostgreSQL"),
    ("restore", "Restore database"),
    ("start-app", "Start CMS"),
    ("health", "Health check"),
    ("verify-records", "Verify records against manifest"),
    ("report", "Recovery report"),
]
TEARDOWN_STEPS = [
    ("preflight", "Preflight checks"),
    ("plan", "Terraform plan and safety check"),
    ("approval", "Operator approval"),
    ("destroy", "Remove recovery environment"),
    ("confirm", "Confirm nothing is left running"),
]


def utcnow() -> datetime:
    return datetime.now(UTC)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).astimezone(UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def new_job_id(now: datetime | None = None) -> str:
    return f"job-{(now or utcnow()).strftime('%Y%m%dT%H%M%SZ')}-{secrets.token_hex(3)}"


@dataclass
class Step:
    id: str
    title: str
    status: str = "pending"  # pending | running | ok | failed | skipped
    started_at: str | None = None
    finished_at: str | None = None
    detail: str = ""


@dataclass
class Job:
    id: str
    type: str
    status: str
    created_at: str
    backup_id: str | None = None
    declared_at: str | None = None  # drill: incident declared, RTO timer starts
    approved_at: str | None = None
    finished_at: str | None = None
    app_git_ref: str | None = None
    plan: dict[str, Any] | None = None
    steps: list[Step] = field(default_factory=list)
    host_events: list[dict[str, Any]] = field(default_factory=list)
    result: dict[str, Any] | None = None
    error: str | None = None

    def step(self, step_id: str) -> Step:
        return next(s for s in self.steps if s.id == step_id)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Job:
        d = dict(d)
        d["steps"] = [Step(**s) for s in d.get("steps", [])]
        return cls(**d)


class JobError(RuntimeError):
    def __init__(self, code: str, message: str, status: int = 409):
        super().__init__(message)
        self.code = code
        self.status = status


class JobStore:
    """One folder per job (job.json, Terraform plan files) plus a shared, append-only audit.jsonl."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def job_dir(self, job_id: str) -> Path:
        if not JOB_ID_RE.match(job_id):
            raise JobError("unknown-job", "invalid job id", 404)
        return self.root / job_id

    def save(self, job: Job) -> None:
        with self._lock:
            d = self.job_dir(job.id)
            d.mkdir(exist_ok=True)
            tmp = d / ".job.json.tmp"
            tmp.write_text(json.dumps(job.to_dict(), indent=2), encoding="utf-8")
            os.replace(tmp, d / "job.json")

    def load(self, job_id: str) -> Job:
        path = self.job_dir(job_id) / "job.json"
        if not path.exists():
            raise JobError("unknown-job", f"no job {job_id}", 404)
        return Job.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def all(self) -> list[Job]:
        jobs = [self.load(p.name) for p in self.root.iterdir() if p.is_dir() and JOB_ID_RE.match(p.name) and (p / "job.json").exists()]
        return sorted(jobs, key=lambda j: j.created_at, reverse=True)

    def audit(self, action: str, *, job_id: str | None = None, actor: str = "admin", detail: str = "") -> None:
        entry = {"at": iso(), "actor": actor, "action": action, "job_id": job_id, "detail": detail}
        with self._lock, (self.root / "audit.jsonl").open("a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry) + "\n")

    def audit_log(self, limit: int = 500) -> list[dict[str, Any]]:
        path = self.root / "audit.jsonl"
        if not path.exists():
            return []
        out = []
        for line in path.read_text(encoding="utf-8").splitlines()[-limit:]:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return out
