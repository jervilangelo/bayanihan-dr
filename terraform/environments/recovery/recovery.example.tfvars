# Copy to recovery.tfvars (git-ignored) and adjust. Values here are examples, not secrets.

# Keep false except during an approved drill. true adds the VPC and the EC2 recovery host (paid while running).
recovery_enabled = false

# Restore a specific verified backup; omit (null) for the newest verified one.
# recovery_point_id = "20261104T070000Z"

instance_type      = "t3.small"
log_retention_days = 7

# Cost alerts (AWS Budgets). Alerts only: they never stop charges.
# budget_alert_email = "you@example.com"
budget_limit_usd = 10

# Principals allowed to upload backups (decided in Phase 5), e.g. an IAM Identity Center role ARN.
# backup_writer_principal_arns = ["arn:aws:iam::123456789012:role/aws-reserved/sso.amazonaws.com/..."]
