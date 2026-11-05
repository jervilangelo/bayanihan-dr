"""Fail closed unless a Terraform plan does exactly what the job type allows (blueprint §10.2).

A drill may only CREATE the recovery network, host and alarm. A teardown may only DELETE them.
Anything else, such as touching the backup bucket, IAM or the budget, stops the job before approval.
"""

from __future__ import annotations

from typing import Any

DRILL_ADDRESS_PREFIXES = (
    "module.networking[0].",
    "module.compute[0].",
    "module.monitoring.aws_cloudwatch_metric_alarm.recovery_host_status[0]",
)

# On-demand ap-southeast-1 prices, AWS Pricing API, checked 2026-11-05 (docs/evidence/phase5-deployment.md).
HOURLY_USD = {"t3.micro": 0.0132, "t3.small": 0.0264, "t3.medium": 0.0528}
PUBLIC_IPV4_HOURLY_USD = 0.005
GP3_GB_MONTH_USD = 0.096
ALARM_MONTH_USD = 0.10
HOURS_PER_MONTH = 730


class PlanRejected(RuntimeError):
    pass


def _is_drill(address: str) -> bool:
    return address.startswith(DRILL_ADDRESS_PREFIXES)


def summarize(plan_json: dict[str, Any]) -> dict[str, Any]:
    changes = [rc for rc in plan_json.get("resource_changes", []) if rc.get("mode") == "managed"]
    counts = {"create": 0, "update": 0, "delete": 0, "replace": 0}
    resources = []
    for rc in changes:
        actions = rc["change"]["actions"]
        if actions == ["no-op"] or actions == ["read"]:
            continue
        kind = "replace" if set(actions) == {"create", "delete"} else actions[0]
        counts[kind] = counts.get(kind, 0) + 1
        resources.append({"address": rc["address"], "type": rc["type"], "action": kind})
    return {"counts": counts, "resources": resources}


def check(plan_json: dict[str, Any], job_type: str) -> dict[str, Any]:
    summary = summarize(plan_json)
    problems = []
    for r in summary["resources"]:
        if not _is_drill(r["address"]):
            problems.append(f"{r['action']} {r['address']} (outside the drill footprint)")
        elif job_type == "recovery-drill" and r["action"] != "create":
            problems.append(f"{r['action']} {r['address']} (a drill may only create)")
        elif job_type == "teardown" and r["action"] != "delete":
            problems.append(f"{r['action']} {r['address']} (a teardown may only delete)")
    if job_type == "recovery-drill" and not any(r["type"] == "aws_instance" for r in summary["resources"]):
        problems.append("the plan creates no recovery host (is a drill already running?)")
    if job_type == "teardown" and not summary["resources"]:
        problems.append("nothing to remove: no recovery environment is deployed")
    if problems:
        raise PlanRejected("; ".join(problems))
    summary["hourly_cost_usd"] = estimate_hourly(plan_json) if job_type == "recovery-drill" else 0.0
    return summary


def estimate_hourly(plan_json: dict[str, Any]) -> float:
    total = 0.0
    for rc in plan_json.get("resource_changes", []):
        after = (rc.get("change") or {}).get("after") or {}
        if rc.get("type") == "aws_instance" and "create" in rc["change"]["actions"]:
            total += HOURLY_USD.get(after.get("instance_type", ""), 0.05)
            total += PUBLIC_IPV4_HOURLY_USD
            for vol in after.get("root_block_device") or []:
                total += (vol.get("volume_size") or 0) * GP3_GB_MONTH_USD / HOURS_PER_MONTH
        if rc.get("type") == "aws_cloudwatch_metric_alarm" and "create" in rc["change"]["actions"]:
            total += ALARM_MONTH_USD / HOURS_PER_MONTH
    return round(total, 4)
