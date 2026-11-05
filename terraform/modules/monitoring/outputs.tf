output "budget_name" {
  description = "Name of the AWS Budgets cost budget, or null when not created"
  value       = one(aws_budgets_budget.monthly[*].name)
}

output "log_group_arn" {
  description = "ARN of the recovery log group"
  value       = aws_cloudwatch_log_group.recovery.arn
}

output "log_group_name" {
  description = "Name of the recovery log group"
  value       = aws_cloudwatch_log_group.recovery.name
}
