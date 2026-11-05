variable "alarm_action_arns" {
  description = "SNS topic ARNs notified by the instance alarm; empty records the alarm state only"
  type        = list(string)
  default     = []
}

variable "budget_alert_email" {
  description = "Email that receives AWS Budgets alerts; null skips the budget"
  type        = string
  default     = null

  validation {
    condition     = var.budget_alert_email == null || can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.budget_alert_email))
    error_message = "budget_alert_email must be an email address or null."
  }
}

variable "budget_limit_usd" {
  description = "Monthly budget in USD that alerts are measured against (PHP 300-500 is roughly USD 5-9)"
  type        = number
  default     = 10

  validation {
    condition     = var.budget_limit_usd > 0 && var.budget_limit_usd <= 100
    error_message = "budget_limit_usd must be greater than 0 and at most 100."
  }
}

variable "enable_instance_alarm" {
  description = "Create the recovery host status-check alarm (true only while the host exists)"
  type        = bool
  default     = false
}

variable "environment" {
  description = "Environment name used in the log group path"
  type        = string
}

variable "instance_id" {
  description = "Recovery host instance ID for the alarm; required when enable_instance_alarm is true"
  type        = string
  default     = null
}

variable "log_retention_days" {
  description = "Days CloudWatch keeps recovery logs"
  type        = number
  default     = 7

  validation {
    condition     = contains([1, 3, 5, 7, 14, 30], var.log_retention_days)
    error_message = "log_retention_days must be one of 1, 3, 5, 7, 14 or 30 (kept short to bound cost)."
  }
}

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}
