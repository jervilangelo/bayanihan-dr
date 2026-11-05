"""BayanihanDR recovery job runner (System B, Phase 6).

A local, authenticated API on the operator's trusted workstation. It runs a fixed set of job types
(recovery drill, teardown) through a bounded Terraform workflow. It never accepts SQL, shell commands,
file paths or Terraform arguments from a request: only a validated backup ID and an explicit approval.
"""

__version__ = "0.1.0"
