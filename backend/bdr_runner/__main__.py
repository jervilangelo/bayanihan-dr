"""Start the job runner: ``python -m bdr_runner`` (from backend/, with AWS_PROFILE set to the operator role)."""

from __future__ import annotations

import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repository root


def load_token(path: Path) -> str:
    """A random administrator token, created on first start and kept in a git-ignored local file."""
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    token = secrets.token_urlsafe(32)
    path.write_text(token + "\n", encoding="utf-8")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return token


def main() -> int:
    import uvicorn

    from .api import create_app
    from .model import JobStore
    from .ports import AwsBoto, GitRemote, TerraformCli
    from .runner import JobRunner

    tf_dir = ROOT / "terraform" / "environments" / "recovery"
    var_file = tf_dir / "recovery.tfvars"
    if not var_file.exists():
        print(f"missing {var_file} (copy recovery.example.tfvars)", file=sys.stderr)
        return 2
    if not os.environ.get("AWS_PROFILE"):
        print("set AWS_PROFILE to the operator SSO profile (for example bayanihan-dr-dev)", file=sys.stderr)
        return 2

    var_dir = ROOT / "backend" / "var"
    terraform = TerraformCli(workdir=tf_dir, var_file=var_file)
    outputs = terraform.outputs()
    aws = AwsBoto(bucket=outputs["backup_bucket_name"], prefix="backups/", log_group=outputs["recovery_log_group_name"])
    runner = JobRunner(JobStore(var_dir / "jobs"), terraform, aws, GitRemote("https://github.com/jervilangelo/bayanihan-dr.git"))
    token = load_token(var_dir / "admin-token")
    status_file = ROOT / "backups" / "status.json"

    def read_status():
        return json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else None

    print(f"BayanihanDR job runner on http://127.0.0.1:8787  (admin token in {var_dir / 'admin-token'})")
    uvicorn.run(create_app(runner, aws, token, read_status), host="127.0.0.1", port=8787, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
