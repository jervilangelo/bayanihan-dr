variable "ami_ssm_parameter" {
  description = "Public SSM parameter that resolves to the current Amazon Linux 2023 AMI"
  type        = string
  default     = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

variable "backup_bucket_name" {
  description = "Backup bucket the host restores from"
  type        = string
}

variable "backup_prefix" {
  description = "Key prefix under which backups are stored"
  type        = string
}

variable "instance_profile_name" {
  description = "IAM instance profile for the host"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type; small x86_64 burstable types only, to keep drills cheap"
  type        = string
  default     = "t3.small"

  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
    error_message = "instance_type must be t3.micro, t3.small or t3.medium."
  }
}

variable "log_group_name" {
  description = "CloudWatch log group the bootstrap and recovery logs go to"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "recovery_point_id" {
  description = "Backup ID to restore (for example 20261104T070000Z); null means the newest verified backup"
  type        = string
  default     = null

  validation {
    condition     = var.recovery_point_id == null || can(regex("^[0-9]{8}T[0-9]{6}Z$", var.recovery_point_id))
    error_message = "recovery_point_id must look like 20261104T070000Z."
  }
}

variable "region" {
  description = "AWS region, passed to the bootstrap script"
  type        = string
}

variable "root_volume_size_gb" {
  description = "Size of the encrypted gp3 root volume in GiB"
  type        = number
  default     = 20

  validation {
    condition     = var.root_volume_size_gb >= 8 && var.root_volume_size_gb <= 50
    error_message = "root_volume_size_gb must be between 8 and 50."
  }
}

variable "security_group_ids" {
  description = "Security groups attached to the host"
  type        = list(string)
}

variable "subnet_id" {
  description = "Subnet the host runs in"
  type        = string
}
