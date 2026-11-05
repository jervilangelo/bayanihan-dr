output "public_subnet_id" {
  description = "ID of the public subnet the recovery host runs in"
  value       = aws_subnet.public.id
}

output "recovery_host_security_group_id" {
  description = "ID of the recovery host security group (no inbound rules)"
  value       = aws_security_group.recovery_host.id
}

output "s3_endpoint_id" {
  description = "ID of the S3 gateway endpoint"
  value       = aws_vpc_endpoint.s3.id
}

output "vpc_id" {
  description = "ID of the recovery VPC"
  value       = aws_vpc.main.id
}
