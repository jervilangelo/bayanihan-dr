"""Render the EC2 bootstrap template the way Terraform's templatefile() does, so ShellCheck can lint it.

Usage: python scripts/validation/render_bootstrap.py <template.tftpl> <out.sh>
Fails if the template uses a variable this script does not know (keep VALUES in sync with modules/compute/main.tf).
"""
import re
import sys
from pathlib import Path

template = Path(sys.argv[1]).read_text(encoding="utf-8")
values = {
    "app_git_ref": "f" * 40,
    "app_repo_url": "https://github.com/x/y.git",
    "backup_bucket": "b",
    "backup_prefix": "backups/",
    "job_id": "job-20261105T060000Z-a1b2c3",
    "log_group_name": "/bayanihandr/recovery/recovery",
    "recovery_point_id": "20261105T055524Z",
    "region": "ap-southeast-1",
}
rendered = re.sub(r"(?<!\$)\$\{([a-z_]+)\}", lambda m: values[m.group(1)], template).replace("$${", "${")
assert "%{" not in rendered
out = Path(sys.argv[2])
out.write_text(rendered, encoding="utf-8", newline="\n")
print(f"rendered {len(rendered.encode())} bytes (EC2 user data limit 16384)")
