variable "ami_ssm_parameter" {
  description = "Public SSM parameter that resolves to the current Amazon Linux 2023 AMI"
  type        = string
  default     = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

variable "app_git_ref" {
  description = "Full Git commit SHA of the CMS source the host builds (pinned for a reproducible recovery)"
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.app_git_ref))
    error_message = "app_git_ref must be a full 40-character commit SHA."
  }
}

variable "app_repo_url" {
  description = "Public HTTPS Git repository holding the CMS source"
  type        = string
  default     = "https://github.com/jervilangelo/bayanihan-dr.git"

  validation {
    condition     = can(regex("^https://github\\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\\.git$", var.app_repo_url))
    error_message = "app_repo_url must be an https://github.com/<owner>/<repo>.git URL."
  }
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

variable "job_id" {
  description = "Recovery job ID; also the CloudWatch log stream the host reports to"
  type        = string

  validation {
    condition     = can(regex("^job-[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}$", var.job_id))
    error_message = "job_id must look like job-20261105T060000Z-a1b2c3."
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
  description = "Verified off-site backup ID to restore, for example 20261104T070000Z"
  type        = string

  validation {
    condition     = can(regex("^[0-9]{8}T[0-9]{6}Z$", var.recovery_point_id))
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
