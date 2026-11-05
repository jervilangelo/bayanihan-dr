output "backup_writer_role_arn" {
  description = "ARN of the backup-writer role, or null when it is not created"
  value       = one(aws_iam_role.backup_writer[*].arn)
}

output "recovery_host_instance_profile_name" {
  description = "Instance profile name for the recovery host"
  value       = aws_iam_instance_profile.recovery_host.name
}

output "recovery_host_role_arn" {
  description = "ARN of the recovery host role"
  value       = aws_iam_role.recovery_host.arn
}
