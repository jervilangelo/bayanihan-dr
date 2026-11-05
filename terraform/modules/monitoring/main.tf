# Logs and the few alerts worth paying for (blueprint §8.1, §16): short log retention, one instance health
# alarm while a recovery host exists, and an AWS Budgets cost alert. Budgets alert; they never stop charges.

# Accepted (ADR-012): CloudWatch encrypts logs by default; a customer managed key adds cost for synthetic data.
#trivy:ignore:AWS-0017
resource "aws_cloudwatch_log_group" "recovery" {
  name              = "/bayanihandr/${var.environment}/recovery"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_metric_alarm" "recovery_host_status" {
  count = var.enable_instance_alarm ? 1 : 0

  alarm_name          = "${var.name_prefix}-recovery-host-status-check"
  alarm_description   = "The recovery host failed an EC2 status check"
  namespace           = "AWS/EC2"
  metric_name         = "StatusCheckFailed"
  statistic           = "Maximum"
  period              = 60
  evaluation_periods  = 2
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "breaching"
  alarm_actions       = var.alarm_action_arns
  ok_actions          = var.alarm_action_arns

  dimensions = {
    InstanceId = var.instance_id
  }
}

resource "aws_budgets_budget" "monthly" {
  count = var.budget_alert_email == null ? 0 : 1

  name         = "${var.name_prefix}-monthly-cost"
  budget_type  = "COST"
  limit_amount = format("%.2f", var.budget_limit_usd)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = { actual_50 = ["ACTUAL", 50], actual_100 = ["ACTUAL", 100], forecast_100 = ["FORECASTED", 100] }

    content {
      comparison_operator        = "GREATER_THAN"
      notification_type          = notification.value[0]
      threshold                  = notification.value[1]
      threshold_type             = "PERCENTAGE"
      subscriber_email_addresses = [var.budget_alert_email]
    }
  }
}
