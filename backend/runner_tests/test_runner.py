"""Job runner tests with fake Terraform/AWS/Git: no credentials, no infrastructure."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from bdr_runner import planguard
from bdr_runner.api import create_app
from bdr_runner.model import JobError, JobStore
from bdr_runner.runner import JobRunner

TOKEN = "test-token-0123456789"
POINT = {
    "id": "20261105T055524Z",
    "scheduledAt": "2026-11-05T05:55:24Z",
    "sizeBytes": 96669,
    "sha256": "06" * 32,
    "schemaRevision": "0001",
    "records": {"farmers": 1050, "inventory_items": 26, "transactions": 3001},
}
SHA = "f1f86cb8279e22092b2cd85553adae7d162420b2"


def rc(address: str, rtype: str, actions: list[str], after: dict | None = None) -> dict[str, Any]:
    return {"address": address, "type": rtype, "mode": "managed", "change": {"actions": actions, "after": after or {}}}


DRILL_PLAN = {
    "resource_changes": [
        rc("module.storage.aws_s3_bucket.backups", "aws_s3_bucket", ["no-op"]),
        rc("module.networking[0].aws_vpc.main", "aws_vpc", ["create"]),
        rc("module.networking[0].aws_subnet.public", "aws_subnet", ["create"]),
        rc(
            "module.compute[0].aws_instance.recovery_host",
            "aws_instance",
            ["create"],
            {"instance_type": "t3.small", "root_block_device": [{"volume_size": 20}]},
        ),
        rc("module.monitoring.aws_cloudwatch_metric_alarm.recovery_host_status[0]", "aws_cloudwatch_metric_alarm", ["create"]),
    ]
}
TEARDOWN_PLAN = {
    "resource_changes": [
        rc("module.networking[0].aws_vpc.main", "aws_vpc", ["delete"]),
        rc("module.compute[0].aws_instance.recovery_host", "aws_instance", ["delete"]),
        rc("module.storage.aws_s3_bucket.backups", "aws_s3_bucket", ["no-op"]),
    ]
}


def host_ok_events(job_id: str, t0_ms: int) -> list[dict[str, Any]]:
    steps = ["install", "fetch-app", "download", "verify-checksum", "start-db", "restore", "start-app", "health", "verify-records"]
    evs = []
    for i, s in enumerate(steps):
        evs.append({"job_id": job_id, "step": s, "status": "running", "detail": s, "at_ms": t0_ms + i * 20_000})
        evs.append({"job_id": job_id, "step": s, "status": "ok", "detail": f"{s} ok", "at_ms": t0_ms + i * 20_000 + 10_000, **({"restore_ms": 900} if s == "restore" else {})})
    evs.append({"job_id": job_id, "step": "recovery-complete", "status": "ok", "detail": "done", "at_ms": t0_ms + 200_000,
                "restored": POINT["records"], "expected": POINT["records"], "mismatches": {}})
    return evs


class FakeTerraform:
    def __init__(self, plan: dict | None = None, fail_apply: bool = False):
        self.plans: list[dict[str, str]] = []
        self.applied: list[Path] = []
        self.next_plan = plan
        self.fail_apply = fail_apply

    def plan(self, out_file: Path, variables: dict[str, str]) -> dict:
        self.plans.append(variables)
        out_file.write_text("fake plan")
        if self.next_plan is not None:
            return self.next_plan
        return DRILL_PLAN if variables.get("recovery_enabled") == "true" else TEARDOWN_PLAN

    def apply(self, plan_file: Path) -> None:
        assert plan_file.exists(), "apply must use the saved, reviewed plan file"
        if self.fail_apply:
            from bdr_runner.ports import PortError

            raise PortError("terraform apply failed: Error: UnauthorizedOperation")
        self.applied.append(plan_file)

    def outputs(self) -> dict:
        return {}


class FakeAws:
    def __init__(self, arn: str = "arn:aws:sts::123456789012:assumed-role/AWSReservedSSO_BayanihanDR-Developer-V5_abc/op"):
        self.arn = arn
        self.instances = 0
        self.events: dict[str, list] = {}
        self.points = [POINT]

    def identity_arn(self) -> str:
        return self.arn

    def recovery_points(self) -> list[dict]:
        return self.points

    def host_events(self, job_id: str) -> list[dict]:
        return self.events.get(job_id, [])

    def running_instances(self) -> int:
        return self.instances


class FakeGit:
    def remote_head(self) -> str:
        return SHA


@pytest.fixture
def parts(tmp_path):
    store = JobStore(tmp_path / "jobs")
    tf, aws = FakeTerraform(), FakeAws()
    runner = JobRunner(store, tf, aws, FakeGit(), background=False, poll_s=0, sleep=lambda s: None, restore_timeout_s=5)
    return runner, tf, aws


def finish_host(aws: FakeAws, job_id: str, declared_ms: int) -> None:
    aws.events[job_id] = host_ok_events(job_id, declared_ms + 120_000)


# ---------- state machine ----------

def test_drill_stops_for_approval_with_a_guarded_plan(parts):
    runner, tf, _ = parts
    job = runner.create("recovery-drill", POINT["id"])
    assert job.status == "awaiting-approval"
    assert tf.plans == [{"recovery_enabled": "true", "recovery_point_id": POINT["id"], "recovery_job_id": job.id, "app_git_ref": SHA}]
    assert tf.applied == [], "nothing may be applied before approval"
    assert job.plan["counts"]["create"] == 4 and job.plan["hourly_cost_usd"] == pytest.approx(0.034, abs=0.002)
    assert job.step("approval").status == "running"


def test_approved_drill_provisions_restores_and_reports(parts):
    runner, tf, aws = parts
    job = runner.create("recovery-drill", POINT["id"])
    declared_ms = int(time.mktime(time.strptime(job.declared_at[:19], "%Y-%m-%dT%H:%M:%S")) * 1000 - time.timezone * 1000)
    finish_host(aws, job.id, declared_ms)
    job = runner.approve(job.id, job.id)
    assert job.status == "succeeded", job.error
    assert len(tf.applied) == 1
    assert all(s.status == "ok" for s in job.steps), [(s.id, s.status) for s in job.steps]
    r = job.result
    assert r["simulated"] is False and r["within_rto"] and r["rto_seconds"] == pytest.approx(320, abs=2)
    assert r["records"]["restored"] == POINT["records"] and r["restore_ms"] == 900
    actions = [a["action"] for a in runner.store.audit_log()]
    assert actions == ["job-created", "plan-ready", "job-approved", "job-succeeded"]


def test_approval_requires_typing_the_job_id(parts):
    runner, tf, _ = parts
    job = runner.create("recovery-drill", POINT["id"])
    with pytest.raises(JobError) as e:
        runner.approve(job.id, "job-20991231T000000Z-ffffff")
    assert e.value.code == "confirmation-mismatch" and tf.applied == []


def test_only_one_active_job(parts):
    runner, _, _ = parts
    runner.create("recovery-drill", POINT["id"])
    with pytest.raises(JobError) as e:
        runner.create("teardown")
    assert e.value.code == "job-already-running"


def test_cancel_before_apply_and_not_after(parts):
    runner, tf, aws = parts
    job = runner.cancel(runner.create("recovery-drill", POINT["id"]).id)
    assert job.status == "cancelled" and tf.applied == []
    job = runner.create("recovery-drill", POINT["id"])
    finish_host(aws, job.id, 0)
    runner.approve(job.id, job.id)
    with pytest.raises(JobError) as e:
        runner.cancel(job.id)
    assert e.value.code == "cannot-cancel"


@pytest.mark.parametrize(
    "setup, code_or_text",
    [
        (lambda aws: setattr(aws, "arn", "arn:aws:sts::1:assumed-role/AWSReservedSSO_AmplifyDeploy_x/op"), "not the BayanihanDR-Developer"),
        (lambda aws: setattr(aws, "instances", 1), "already exist"),
        (lambda aws: setattr(aws, "points", []), "not a verified off-site backup"),
    ],
)
def test_preflight_fails_closed(parts, setup, code_or_text):
    runner, tf, aws = parts
    setup(aws)
    job = runner.create("recovery-drill", POINT["id"])
    assert job.status == "failed" and code_or_text in job.error
    assert tf.plans == [] and tf.applied == []


def test_unexpected_plan_is_rejected_before_approval(parts):
    runner, tf, _ = parts
    tf.next_plan = {"resource_changes": [*DRILL_PLAN["resource_changes"], rc("module.storage.aws_s3_bucket.backups", "aws_s3_bucket", ["delete", "create"])]}
    job = runner.create("recovery-drill", POINT["id"])
    assert job.status == "failed" and "outside the drill footprint" in job.error and tf.applied == []


def test_host_failure_fails_the_job_with_the_hosts_reason(parts):
    runner, _, aws = parts
    job = runner.create("recovery-drill", POINT["id"])
    aws.events[job.id] = [
        {"step": "download", "status": "ok", "detail": "ok", "at_ms": 1},
        {"step": "verify-checksum", "status": "failed", "detail": "SHA-256 mismatch", "at_ms": 2},
    ]
    job = runner.approve(job.id, job.id)
    assert job.status == "failed" and "verify-checksum failed: SHA-256 mismatch" in job.error
    assert job.step("verify-checksum").status == "failed"


def test_restore_timeout(parts):
    runner, _, _ = parts
    runner.restore_timeout_s = 0
    job = runner.create("recovery-drill", POINT["id"])
    job = runner.approve(job.id, job.id)
    assert job.status == "failed" and "no verified recovery within" in job.error


def test_apply_failure_is_recorded(parts):
    runner, tf, _ = parts
    tf.fail_apply = True
    job = runner.create("recovery-drill", POINT["id"])
    job = runner.approve(job.id, job.id)
    assert job.status == "failed" and "UnauthorizedOperation" in job.error and job.step("provision").status == "failed"


def test_teardown_deletes_only_the_drill_footprint(parts):
    runner, tf, aws = parts
    aws.instances = 1
    job = runner.create("teardown")
    assert job.status == "awaiting-approval" and tf.plans[-1] == {"recovery_enabled": "false"}
    aws.instances = 0
    job = runner.approve(job.id, job.id)
    assert job.status == "succeeded" and job.step("confirm").status == "ok"


def test_interrupted_jobs_are_failed_on_restart(tmp_path):
    store = JobStore(tmp_path / "jobs")
    r1 = JobRunner(store, FakeTerraform(), FakeAws(), FakeGit(), background=False, poll_s=0, sleep=lambda s: None)
    job = r1.create("recovery-drill", POINT["id"])
    j = store.load(job.id)
    j.status = "restoring"
    store.save(j)
    JobRunner(store, FakeTerraform(), FakeAws(), FakeGit(), background=False)
    j = store.load(job.id)
    assert j.status == "failed" and "run a teardown" in j.error


# ---------- plan guard ----------

def test_planguard_rejects_teardown_that_touches_backups():
    plan = {"resource_changes": [rc("module.storage.aws_s3_bucket.backups", "aws_s3_bucket", ["delete"])]}
    with pytest.raises(planguard.PlanRejected, match="outside the drill footprint"):
        planguard.check(plan, "teardown")


def test_planguard_rejects_drill_updates_and_empty_drills():
    plan = {"resource_changes": [rc("module.compute[0].aws_instance.recovery_host", "aws_instance", ["update"])]}
    with pytest.raises(planguard.PlanRejected, match="may only create"):
        planguard.check(plan, "recovery-drill")
    with pytest.raises(planguard.PlanRejected, match="no recovery host"):
        planguard.check({"resource_changes": []}, "recovery-drill")


# ---------- HTTP API ----------

@pytest.fixture
def client(parts):
    runner, _, aws = parts
    app = create_app(runner, aws, TOKEN, lambda: {"schemaVersion": 1, "backups": []})
    return TestClient(app, base_url="http://127.0.0.1:8787")


AUTH = {"Authorization": f"Bearer {TOKEN}"}


def test_api_requires_the_token(client):
    assert client.get("/health").status_code == 200
    assert client.get("/api/jobs").status_code == 401
    assert client.get("/api/jobs", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/jobs", headers=AUTH).status_code == 200


def test_api_rejects_foreign_origins_and_hosts(client):
    assert client.post("/api/jobs", json={"type": "teardown"}, headers={**AUTH, "Origin": "https://evil.example"}).status_code == 403
    assert client.get("/health", headers={"Host": "attacker.example"}).status_code == 400
    assert client.get("/api/jobs", headers={**AUTH, "Origin": "http://localhost:5173"}).status_code == 200


def test_api_validates_inputs(client):
    assert client.post("/api/jobs", json={"type": "shell", "backup_id": "x"}, headers=AUTH).status_code == 422
    assert client.post("/api/jobs", json={"type": "recovery-drill", "backup_id": "../../etc"}, headers=AUTH).status_code == 422
    assert client.get("/api/jobs/not-a-job", headers=AUTH).status_code == 404


def test_api_drill_flow(client, parts):
    _, tf, aws = parts
    job = client.post("/api/jobs", json={"type": "recovery-drill", "backup_id": POINT["id"]}, headers=AUTH).json()
    assert job["status"] == "awaiting-approval"
    assert client.post("/api/jobs", json={"type": "teardown"}, headers=AUTH).json()["code"] == "job-already-running"
    bad = client.post(f"/api/jobs/{job['id']}/approve", json={"confirm_job_id": "job-20991231T000000Z-ffffff"}, headers=AUTH)
    assert bad.status_code == 422 and tf.applied == []
    finish_host(aws, job["id"], 0)
    done = client.post(f"/api/jobs/{job['id']}/approve", json={"confirm_job_id": job["id"]}, headers=AUTH).json()
    assert done["status"] == "succeeded"
    audit = client.get("/api/audit", headers=AUTH).json()
    assert audit[0]["action"] == "job-succeeded"
