"""The job state machine (blueprint §10): preflight, guarded plan, explicit approval, apply, watch, report."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

from . import planguard
from .model import (
    ACTIVE,
    BACKUP_ID_RE,
    DRILL_STEPS,
    JOB_TYPES,
    TEARDOWN_STEPS,
    Job,
    JobError,
    JobStore,
    Step,
    iso,
    new_job_id,
    utcnow,
)
from .ports import AwsPort, GitPort, PortError, TerraformPort

HOST_STEP_IDS = {s for s, _ in DRILL_STEPS[4:13]}


class _Cancelled(Exception):
    """The operator cancelled the job while it was being prepared."""


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _ms_iso(ms: int) -> str:
    return iso(datetime.fromtimestamp(ms / 1000, tz=utcnow().tzinfo))


class JobRunner:
    def __init__(
        self,
        store: JobStore,
        terraform: TerraformPort,
        aws: AwsPort,
        git: GitPort,
        *,
        required_role_marker: str = "BayanihanDR-Developer",
        rto_target_minutes: int = 30,
        rpo_target_minutes: int = 60,
        restore_timeout_s: int = 1800,
        poll_s: float = 10.0,
        background: bool = True,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.store = store
        self.tf = terraform
        self.aws = aws
        self.git = git
        self.role_marker = required_role_marker
        self.rto_target = rto_target_minutes
        self.rpo_target = rpo_target_minutes
        self.restore_timeout_s = restore_timeout_s
        self.poll_s = poll_s
        self.background = background
        self.sleep = sleep
        self._lock = threading.RLock()
        self._recover_interrupted()

    # ---------- public operations (each is audited) ----------

    def create(self, job_type: str, backup_id: str | None = None) -> Job:
        if job_type not in JOB_TYPES:
            raise JobError("invalid-job-type", f"unknown job type {job_type!r}", 422)
        if job_type == "recovery-drill" and (not backup_id or not BACKUP_ID_RE.match(backup_id)):
            raise JobError("invalid-recovery-point", "a drill needs a backup ID like 20261104T070000Z", 422)
        if job_type == "teardown" and backup_id is not None:
            raise JobError("invalid-request", "a teardown takes no backup ID", 422)
        with self._lock:
            active = self.active()
            if active:
                raise JobError("job-already-running", f"job {active.id} is still {active.status}")
            now = utcnow()
            steps = DRILL_STEPS if job_type == "recovery-drill" else TEARDOWN_STEPS
            job = Job(
                id=new_job_id(now),
                type=job_type,
                status="preparing",
                created_at=iso(now),
                backup_id=backup_id,
                declared_at=iso(now) if job_type == "recovery-drill" else None,
                steps=[Step(i, t) for i, t in steps],
            )
            self.store.save(job)
        self.store.audit("job-created", job_id=job.id, detail=f"{job_type}" + (f" from {backup_id}" if backup_id else ""))
        self._spawn(self._prepare, job.id)
        return self.store.load(job.id)

    def approve(self, job_id: str, confirm_job_id: str) -> Job:
        with self._lock:
            job = self.store.load(job_id)
            if confirm_job_id != job_id:
                raise JobError("confirmation-mismatch", "type the job ID exactly to approve it", 422)
            if job.status != "awaiting-approval":
                raise JobError("not-awaiting-approval", f"job is {job.status}")
            job.status = "applying"
            job.approved_at = iso()
            self._finish_step(job, "approval", "ok", "Approved by the administrator")
            self.store.save(job)
        self.store.audit("job-approved", job_id=job_id, detail=f"plan: {job.plan['counts'] if job.plan else {}}")
        self._spawn(self._execute, job_id)
        return self.store.load(job_id)

    def cancel(self, job_id: str) -> Job:
        with self._lock:
            job = self.store.load(job_id)
            if job.status not in ("preparing", "awaiting-approval"):
                raise JobError(
                    "cannot-cancel",
                    f"job is {job.status}; once applying has started, use a teardown job to remove what was created",
                )
            job.status = "cancelled"
            job.finished_at = iso()
            for s in job.steps:
                if s.status in ("pending", "running"):
                    s.status, s.finished_at = "skipped", s.finished_at or iso()
            self.store.save(job)
        self.store.audit("job-cancelled", job_id=job_id, detail="nothing was applied")
        return self.store.load(job_id)

    def active(self) -> Job | None:
        return next((j for j in self.store.all() if j.status in ACTIVE), None)

    # ---------- workers ----------

    def _spawn(self, fn: Callable[[str], None], job_id: str) -> None:
        if self.background:
            threading.Thread(target=fn, args=(job_id,), daemon=True, name=f"{fn.__name__}-{job_id}").start()
        else:
            fn(job_id)

    def _prepare(self, job_id: str) -> None:
        job = self.store.load(job_id)
        try:
            self._start_step(job, "preflight")
            arn = self.aws.identity_arn()
            if self.role_marker not in arn:
                raise JobError("wrong-identity", f"signed in as {arn.split('/')[-2] if '/' in arn else arn}, not the {self.role_marker} role")
            running = self.aws.running_instances()
            variables: dict[str, str]
            if job.type == "recovery-drill":
                if running:
                    raise JobError("drill-running", f"{running} recovery host(s) already exist; run a teardown first")
                points = {p["id"]: p for p in self.aws.recovery_points()}
                point = points.get(job.backup_id or "")
                if not point:
                    raise JobError("not-a-recovery-point", f"{job.backup_id} is not a verified off-site backup")
                job.app_git_ref = self.git.remote_head()
                job.result = {"recovery_point": point}
                detail = f"Identity OK; {job.backup_id} verified off-site; CMS source {job.app_git_ref[:12]}"
                variables = {
                    "recovery_enabled": "true",
                    "recovery_point_id": job.backup_id or "",
                    "recovery_job_id": job.id,
                    "app_git_ref": job.app_git_ref,
                }
            else:
                detail = f"Identity OK; {running} recovery host(s) found"
                variables = {"recovery_enabled": "false"}
            self._finish_step(job, "preflight", "ok", detail)

            self._start_step(job, "plan")
            plan_json = self.tf.plan(self.store.job_dir(job.id) / "tfplan", variables)
            summary = planguard.check(plan_json, job.type)
            job.plan = summary
            c = summary["counts"]
            self._finish_step(job, "plan", "ok", f"{c['create']} to add, {c['update']} to change, {c['delete']} to destroy; matches the {job.type} footprint")
            job.status = "awaiting-approval"
            self._start_step(job, "approval", "Waiting for an administrator to approve the plan")
            self.store.audit("plan-ready", job_id=job.id, detail=f"{c}; est. USD {summary['hourly_cost_usd']}/h")
        except _Cancelled:
            return
        except (JobError, PortError, planguard.PlanRejected) as e:
            self._fail(job.id, str(e))
        except Exception as e:  # never leave a job silently stuck in "preparing"
            self._fail(job.id, f"unexpected error: {type(e).__name__}: {e}")

    def _execute(self, job_id: str) -> None:
        job = self.store.load(job_id)
        try:
            if job.type == "recovery-drill":
                self._start_step(job, "provision")
                self.tf.apply(self.store.job_dir(job.id) / "tfplan")
                self._finish_step(job, "provision", "ok", "Recovery network and host created")
                job.status = "restoring"
                self.store.save(job)
                self._watch_host(job)
                self._report(self.store.load(job.id))
            else:
                self._start_step(job, "destroy")
                self.tf.apply(self.store.job_dir(job.id) / "tfplan")
                self._finish_step(job, "destroy", "ok", "Terraform removed the recovery environment")
                self._start_step(job, "confirm")
                deadline = time.monotonic() + 300
                while (left := self.aws.running_instances()) and time.monotonic() < deadline:
                    self.sleep(self.poll_s)
                if left:
                    raise JobError("teardown-incomplete", f"{left} recovery host(s) still exist after teardown")
                self._finish_step(job, "confirm", "ok", "No recovery hosts remain; backups and IAM untouched")
                self._succeed(job, "teardown complete")
        except (JobError, PortError) as e:
            self._fail(job.id, str(e))
        except Exception as e:
            self._fail(job.id, f"unexpected error: {type(e).__name__}: {e}")

    def _watch_host(self, job: Job) -> None:
        deadline = time.monotonic() + self.restore_timeout_s
        while True:
            events = self.aws.host_events(job.id)
            job = self.store.load(job.id)
            job.host_events = events
            for ev in events:
                sid = ev.get("step")
                if sid not in HOST_STEP_IDS:
                    continue
                step = job.step(sid)
                at = _ms_iso(ev["at_ms"])
                if ev["status"] == "running" and step.status == "pending":
                    step.status, step.started_at, step.detail = "running", at, ev.get("detail", "")
                elif ev["status"] in ("ok", "failed"):
                    step.status, step.finished_at, step.detail = ev["status"], at, ev.get("detail", "")
                    step.started_at = step.started_at or at
            self.store.save(job)
            failed = next((e for e in events if e.get("status") == "failed"), None)
            if failed:
                raise JobError("restore-failed", f"host step {failed.get('step')} failed: {failed.get('detail')}")
            if any(e.get("step") == "recovery-complete" and e.get("status") == "ok" for e in events):
                return
            if time.monotonic() > deadline:
                raise JobError("restore-timeout", f"no verified recovery within {self.restore_timeout_s // 60} minutes")
            self.sleep(self.poll_s)

    def _report(self, job: Job) -> None:
        self._start_step(job, "report")
        done = next(e for e in job.host_events if e.get("step") == "recovery-complete")
        declared = _parse(job.declared_at or job.created_at)
        recovered_ms = done["at_ms"]
        point = (job.result or {}).get("recovery_point", {})
        backup_time = _parse(point["scheduledAt"])
        rto_s = round(recovered_ms / 1000 - declared.timestamp(), 1)
        rpo_s = round(declared.timestamp() - backup_time.timestamp(), 1)
        steps = {s.id: s for s in job.steps}

        def dur(a: str, b: str) -> float | None:
            sa, sb = steps[a].started_at, steps[b].finished_at
            return round((_parse(sb) - _parse(sa)).total_seconds(), 1) if sa and sb else None

        job.result = {
            **(job.result or {}),
            "simulated": False,
            "declared_at": job.declared_at,
            "approved_at": job.approved_at,
            "recovered_at": _ms_iso(recovered_ms),
            "rto_seconds": rto_s,
            "rpo_seconds": rpo_s,
            "rto_target_seconds": self.rto_target * 60,
            "rpo_target_seconds": self.rpo_target * 60,
            "within_rto": rto_s <= self.rto_target * 60,
            "within_rpo": rpo_s <= self.rpo_target * 60,
            "approval_wait_seconds": round((_parse(job.approved_at) - declared).total_seconds(), 1) if job.approved_at else None,
            "provision_seconds": dur("provision", "provision"),
            "host_seconds": dur("install", "verify-records"),
            "restore_ms": next((e.get("restore_ms") for e in job.host_events if e.get("step") == "restore" and e.get("status") == "ok"), None),
            "records": {"restored": done.get("restored"), "expected": done.get("expected")},
            "clock_note": "RTO uses the recovery host's clock (Amazon Time Sync) against this workstation's clock.",
        }
        self._finish_step(job, "report", "ok", f"RTO {rto_s / 60:.1f} min (target {self.rto_target}), RPO {rpo_s / 60:.1f} min (target {self.rpo_target})")
        self._succeed(job, "recovery verified")

    # ---------- helpers ----------

    def _save(self, job: Job) -> None:
        """Save, unless the operator cancelled the job meanwhile (then stop the worker)."""
        with self._lock:
            if self.store.load(job.id).status == "cancelled":
                raise _Cancelled()
            self.store.save(job)

    def _start_step(self, job: Job, step_id: str, detail: str = "") -> None:
        s = job.step(step_id)
        s.status, s.started_at, s.detail = "running", iso(), detail
        self._save(job)

    def _finish_step(self, job: Job, step_id: str, status: str, detail: str) -> None:
        s = job.step(step_id)
        s.status, s.finished_at, s.detail = status, iso(), detail
        s.started_at = s.started_at or s.finished_at
        self._save(job)

    def _succeed(self, job: Job, why: str) -> None:
        job.status, job.finished_at = "succeeded", iso()
        self.store.save(job)
        self.store.audit("job-succeeded", job_id=job.id, detail=why)

    def _fail(self, job_id: str, reason: str) -> None:
        job = self.store.load(job_id)
        if job.status == "cancelled":
            return
        job.status, job.error, job.finished_at = "failed", reason[:900], iso()
        for s in job.steps:
            if s.status == "running":
                s.status, s.finished_at, s.detail = "failed", iso(), reason[:300]
        self.store.save(job)
        self.store.audit("job-failed", job_id=job_id, detail=reason[:300])

    def _recover_interrupted(self) -> None:
        """A job left active by a crash or restart is failed loudly, never resumed blindly."""
        for job in self.store.all():
            if job.status in ACTIVE:
                applied = job.status in ("applying", "restoring")
                self._fail(
                    job.id,
                    "the job runner stopped while this job was active"
                    + ("; resources may exist: check AWS and run a teardown" if applied else "; nothing was applied"),
                )

    def overview(self) -> dict[str, Any]:
        active = self.active()
        return {"active_job": active.to_dict() if active else None}
