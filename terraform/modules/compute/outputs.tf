output "instance_id" {
  description = "ID of the recovery host (use with: aws ssm start-session --target <id>)"
  value       = aws_instance.recovery_host.id
}

output "private_ip" {
  description = "Private IPv4 address of the recovery host"
  value       = aws_instance.recovery_host.private_ip
}
