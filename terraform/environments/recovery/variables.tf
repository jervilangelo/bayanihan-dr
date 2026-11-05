variable "availability_zone" {
  description = "Availability zone for the recovery subnet; null picks the first available zone"
  type        = string
  default     = null
}

variable "aws_region" {
  description = "AWS region; fixed to Singapore by the blueprint (closest region to Naga City)"
  type        = string
  default     = "ap-southeast-1"

  validation {
    condition     = var.aws_region == "ap-southeast-1"
    error_message = "The blueprint fixes the recovery region to ap-southeast-1."
  }
}

variable "backup_bucket_name" {
  description = "Override for the backup bucket name; null derives it from the account ID and region"
  type        = string
  default     = null
}

variable "backup_noncurrent_retention_days" {
  description = "Days an overwritten or deleted backup version is kept in S3"
  type        = number
  default     = 7
}

variable "backup_retention_days" {
  description = "Days a backup is kept in S3 before it expires"
  type        = number
  default     = 30
}

variable "backup_writer_principal_arns" {
  description = "IAM principals that may assume the backup-writer role; empty skips the role"
  type        = list(string)
  default     = []
}

variable "budget_alert_email" {
  description = "Email for AWS Budgets cost alerts; null skips the budget"
  type        = string
  default     = null
}

variable "budget_limit_usd" {
  description = "Monthly cost budget in USD for alerts"
  type        = number
  default     = 10
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "recovery"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{1,15}$", var.environment))
    error_message = "environment must be 2-16 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "instance_type" {
  description = "Recovery host instance type; small x86_64 burstable types only"
  type        = string
  default     = "t3.small"

  validation {
    condition     = contains(["t3.micro", "t3.small", "t3.medium"], var.instance_type)
    error_message = "instance_type must be t3.micro, t3.small or t3.medium."
  }
}

variable "log_retention_days" {
  description = "Days CloudWatch keeps recovery logs"
  type        = number
  default     = 7
}

variable "owner" {
  description = "Owner tag applied to every resource"
  type        = string
  default     = "bayanihandr"
}

variable "recovery_enabled" {
  description = "Create the recovery network and host. Keep false except during an approved drill or recovery."
  type        = bool
  default     = false
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
