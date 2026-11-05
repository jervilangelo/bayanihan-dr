output "backup_bucket_name" {
  description = "Name of the encrypted backup bucket"
  value       = module.storage.bucket_name
}

output "backup_writer_role_arn" {
  description = "Role the on-premises backup engine assumes to upload backups, or null"
  value       = module.identity.backup_writer_role_arn
}

output "budget_name" {
  description = "AWS Budgets cost budget, or null when no alert email is set"
  value       = module.monitoring.budget_name
}

output "recovery_enabled" {
  description = "Whether the recovery network and host are part of this configuration"
  value       = var.recovery_enabled
}

output "recovery_host_instance_id" {
  description = "Recovery host instance ID, or null outside a recovery"
  value       = var.recovery_enabled ? module.compute[0].instance_id : null
}

output "recovery_log_group_name" {
  description = "CloudWatch log group for recovery logs"
  value       = module.monitoring.log_group_name
}

output "ssm_session_command" {
  description = "Command to open a shell on the recovery host, or null outside a recovery"
  value       = var.recovery_enabled ? "aws ssm start-session --region ${var.aws_region} --target ${module.compute[0].instance_id}" : null
}
