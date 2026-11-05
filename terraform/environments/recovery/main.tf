# BayanihanDR recovery environment (ap-southeast-1).
#
# Two lifecycles in one configuration:
#   * Always present (small, near-zero idle cost): backup bucket, IAM roles, log group, optional budget alert.
#   * Only while recovery_enabled = true (a drill or a real recovery): VPC, recovery host, health alarm.
# Setting recovery_enabled back to false and applying removes the paid compute without touching backups.

data "aws_caller_identity" "current" {}

data "aws_availability_zones" "available" {
  state = "available"
}

module "storage" {
  source = "../../modules/storage"

  bucket_name                       = local.backup_bucket_name
  current_version_retention_days    = var.backup_retention_days
  noncurrent_version_retention_days = var.backup_noncurrent_retention_days
}

module "monitoring" {
  source = "../../modules/monitoring"

  name_prefix           = local.name_prefix
  environment           = var.environment
  log_retention_days    = var.log_retention_days
  budget_alert_email    = var.budget_alert_email
  budget_limit_usd      = var.budget_limit_usd
  enable_instance_alarm = var.recovery_enabled
  instance_id           = var.recovery_enabled ? module.compute[0].instance_id : null
}

module "identity" {
  source = "../../modules/identity"

  name_prefix                  = local.name_prefix
  backup_bucket_arn            = module.storage.bucket_arn
  backup_prefix                = module.storage.backup_prefix
  log_group_arn                = module.monitoring.log_group_arn
  backup_writer_principal_arns = var.backup_writer_principal_arns
}

module "networking" {
  source = "../../modules/networking"
  count  = var.recovery_enabled ? 1 : 0

  name_prefix       = local.name_prefix
  region            = var.aws_region
  availability_zone = local.availability_zone
}

module "compute" {
  source = "../../modules/compute"
  count  = var.recovery_enabled ? 1 : 0

  name_prefix           = local.name_prefix
  region                = var.aws_region
  instance_type         = var.instance_type
  subnet_id             = module.networking[0].public_subnet_id
  security_group_ids    = [module.networking[0].recovery_host_security_group_id]
  instance_profile_name = module.identity.recovery_host_instance_profile_name
  backup_bucket_name    = module.storage.bucket_name
  backup_prefix         = module.storage.backup_prefix
  log_group_name        = module.monitoring.log_group_name
  recovery_point_id     = var.recovery_point_id
  job_id                = var.recovery_job_id
  app_git_ref           = var.app_git_ref
}

# A recovery must name exactly what it restores and which code it runs: fail at plan time otherwise.
check "recovery_inputs" {
  assert {
    condition     = !var.recovery_enabled || (var.recovery_point_id != null && var.recovery_job_id != null && var.app_git_ref != null)
    error_message = "recovery_enabled = true requires recovery_point_id, recovery_job_id and app_git_ref (the job runner sets them)."
  }
}
