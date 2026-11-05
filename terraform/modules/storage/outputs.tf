output "backup_prefix" {
  description = "Key prefix under which backups are stored"
  value       = var.backup_prefix
}

output "bucket_arn" {
  description = "ARN of the backup bucket"
  value       = aws_s3_bucket.backups.arn
}

output "bucket_name" {
  description = "Name of the backup bucket"
  value       = aws_s3_bucket.backups.bucket
}
