variable "backup_prefix" {
  description = "Key prefix under which backups are stored; must end with a slash"
  type        = string
  default     = "backups/"

  validation {
    condition     = can(regex("^[a-z0-9-]+/$", var.backup_prefix))
    error_message = "backup_prefix must be lowercase letters, digits or hyphens, ending with a slash (for example backups/)."
  }
}

variable "bucket_name" {
  description = "Globally unique name of the backup bucket"
  type        = string

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "bucket_name must be a valid S3 bucket name (3-63 lowercase characters)."
  }
}

variable "current_version_retention_days" {
  description = "Days a backup object is kept before it expires"
  type        = number
  default     = 30

  validation {
    condition     = var.current_version_retention_days >= 7 && var.current_version_retention_days <= 365
    error_message = "current_version_retention_days must be between 7 and 365."
  }
}

variable "kms_key_arn" {
  description = "Customer managed KMS key for SSE-KMS; null uses SSE-S3 (AES256), which has no key cost"
  type        = string
  default     = null
}

variable "noncurrent_version_retention_days" {
  description = "Days an overwritten or deleted backup version is kept"
  type        = number
  default     = 7

  validation {
    condition     = var.noncurrent_version_retention_days >= 1 && var.noncurrent_version_retention_days <= 90
    error_message = "noncurrent_version_retention_days must be between 1 and 90."
  }
}
