variable "aws_region" {
  description = "Region for the state bucket; same region as the recovery environment"
  type        = string
  default     = "ap-southeast-1"
}

variable "noncurrent_state_retention_days" {
  description = "Days old state versions are kept (to roll back a damaged state file)"
  type        = number
  default     = 30

  validation {
    condition     = var.noncurrent_state_retention_days >= 7
    error_message = "Keep old state versions for at least 7 days."
  }
}
