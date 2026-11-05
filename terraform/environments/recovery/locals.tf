locals {
  name_prefix = "bdr-${var.environment}"

  # Account ID and region make the name globally unique without a random suffix.
  backup_bucket_name = coalesce(
    var.backup_bucket_name,
    "bayanihandr-backups-${data.aws_caller_identity.current.account_id}-${var.aws_region}",
  )

  availability_zone = coalesce(var.availability_zone, data.aws_availability_zones.available.names[0])

  common_tags = {
    Project     = "BayanihanDR"
    Environment = var.environment
    ManagedBy   = "Terraform"
    Owner       = var.owner
    DataClass   = "synthetic"
  }
}
