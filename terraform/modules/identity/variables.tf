variable "backup_bucket_arn" {
  description = "ARN of the backup bucket"
  type        = string
}

variable "backup_prefix" {
  description = "Key prefix under which backups are stored, ending with a slash"
  type        = string
}

variable "backup_writer_principal_arns" {
  description = "IAM principals allowed to assume the backup-writer role; empty means the role is not created"
  type        = list(string)
  default     = []

  validation {
    condition     = alltrue([for arn in var.backup_writer_principal_arns : can(regex("^arn:aws[a-z-]*:(iam|sts)::[0-9]{12}:", arn))])
    error_message = "Each backup writer principal must be an IAM or STS ARN."
  }
}

variable "log_group_arn" {
  description = "ARN of the CloudWatch log group the recovery host writes to"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}
