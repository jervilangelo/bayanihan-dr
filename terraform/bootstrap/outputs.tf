output "state_bucket_name" {
  description = "Put this in terraform/environments/recovery/backend.hcl as bucket"
  value       = aws_s3_bucket.state.id
}
