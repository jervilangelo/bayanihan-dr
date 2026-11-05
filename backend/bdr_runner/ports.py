"""Adapters to the outside world. Each command line is fixed here; requests can only fill in validated values."""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .model import BACKUP_ID_RE, JOB_ID_RE, SHA_RE


class PortError(RuntimeError):
    pass


class TerraformPort(Protocol):
    def plan(self, out_file: Path, variables: dict[str, str]) -> dict[str, Any]: ...
    def apply(self, plan_file: Path) -> None: ...
    def outputs(self) -> dict[str, Any]: ...


class AwsPort(Protocol):
    def identity_arn(self) -> str: ...
    def recovery_points(self) -> list[dict[str, Any]]: ...
    def host_events(self, job_id: str) -> list[dict[str, Any]]: ...
    def running_instances(self) -> int: ...


class GitPort(Protocol):
    def remote_head(self) -> str: ...


_ALLOWED_VARS = {
    "recovery_enabled": lambda v: v in ("true", "false"),
    "recovery_point_id": lambda v: bool(BACKUP_ID_RE.match(v)),
    "recovery_job_id": lambda v: bool(JOB_ID_RE.match(v)),
    "app_git_ref": lambda v: bool(SHA_RE.match(v)),
}


@dataclass
class TerraformCli:
    workdir: Path
    var_file: Path
    plan_timeout: int = 900
    apply_timeout: int = 1800

    def _run(self, args: list[str], timeout: int) -> str:
        cmd = ["terraform", f"-chdir={self.workdir}", *args]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, env={**os.environ, "TF_IN_AUTOMATION": "1"})
        except subprocess.TimeoutExpired as e:
            raise PortError(f"terraform {args[0]} timed out after {timeout} s") from e
        if r.returncode != 0:
            tail = [ln for ln in (r.stderr or r.stdout).splitlines() if ln.strip()][-6:]
            raise PortError(f"terraform {args[0]} failed: " + " | ".join(tail)[:900])
        return r.stdout

    def plan(self, out_file: Path, variables: dict[str, str]) -> dict[str, Any]:
        args = ["plan", "-input=false", "-no-color", "-lock-timeout=60s", f"-var-file={self.var_file}", f"-out={out_file}"]
        for k, v in variables.items():
            if k not in _ALLOWED_VARS or not _ALLOWED_VARS[k](v):
                raise PortError(f"refusing Terraform variable {k}")
            args.append(f"-var={k}={v}")
        self._run(args, self.plan_timeout)
        return json.loads(self._run(["show", "-json", "-no-color", str(out_file)], 120))

    def apply(self, plan_file: Path) -> None:
        # A saved plan applies exactly what was reviewed; Terraform refuses it if the state changed since.
        self._run(["apply", "-input=false", "-no-color", "-lock-timeout=60s", str(plan_file)], self.apply_timeout)

    def outputs(self) -> dict[str, Any]:
        raw = json.loads(self._run(["output", "-json", "-no-color"], 120))
        return {k: v.get("value") for k, v in raw.items()}


@dataclass
class AwsBoto:
    bucket: str
    prefix: str
    log_group: str
    region: str = "ap-southeast-1"

    def _client(self, service: str):
        import boto3

        return boto3.session.Session(region_name=self.region).client(service)

    def identity_arn(self) -> str:
        return self._client("sts").get_caller_identity()["Arn"]

    def recovery_points(self) -> list[dict[str, Any]]:
        """Verified backups that exist OFF-SITE (a recovery cannot rely on the failed office)."""
        s3 = self._client("s3")
        points = []
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=self.bucket, Prefix=self.prefix, Delimiter="/"):
            for cp in page.get("CommonPrefixes", []):
                backup_id = cp["Prefix"][len(self.prefix) :].rstrip("/")
                if not BACKUP_ID_RE.match(backup_id):
                    continue
                try:
                    body = s3.get_object(Bucket=self.bucket, Key=f"{cp['Prefix']}manifest.json")["Body"].read()
                    m = json.loads(body)
                except Exception:  # missing or unreadable manifest: not a recovery point
                    continue
                if m.get("status") != "verified" or m.get("backup_id") != backup_id:
                    continue
                points.append(
                    {
                        "id": backup_id,
                        "scheduledAt": m["scheduled_at"],
                        "completedAt": m.get("completed_at"),
                        "sizeBytes": m["archive"]["size_bytes"],
                        "sha256": m["archive"]["sha256"],
                        "schemaRevision": m["source"]["schema_revision"],
                        "records": m.get("records", {}),
                    }
                )
        return sorted(points, key=lambda p: p["scheduledAt"], reverse=True)

    def host_events(self, job_id: str) -> list[dict[str, Any]]:
        logs = self._client("logs")
        events: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {"logGroupName": self.log_group, "logStreamName": job_id, "startFromHead": True}
        try:
            while True:
                page = logs.get_log_events(**kwargs)
                for e in page.get("events", []):
                    try:
                        events.append(json.loads(e["message"]))
                    except json.JSONDecodeError:
                        continue
                token = page.get("nextForwardToken")
                if not page.get("events") or token == kwargs.get("nextToken"):
                    break
                kwargs["nextToken"] = token
        except logs.exceptions.ResourceNotFoundException:
            return []  # the host has not created its stream yet
        return events

    def running_instances(self) -> int:
        ec2 = self._client("ec2")
        r = ec2.describe_instances(
            Filters=[
                {"Name": "tag:Project", "Values": ["BayanihanDR"]},
                {"Name": "instance-state-name", "Values": ["pending", "running", "stopping", "stopped", "shutting-down"]},
            ]
        )
        return sum(len(res["Instances"]) for res in r["Reservations"])


@dataclass
class GitRemote:
    url: str
    branch: str = "main"

    def remote_head(self) -> str:
        r = subprocess.run(["git", "ls-remote", self.url, f"refs/heads/{self.branch}"], capture_output=True, text=True, timeout=60)
        sha = r.stdout.split()[0] if r.returncode == 0 and r.stdout.strip() else ""
        if not SHA_RE.match(sha):
            raise PortError(f"could not resolve {self.url} {self.branch}")
        return sha
