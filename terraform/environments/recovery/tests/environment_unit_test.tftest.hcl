# Plan-only tests of the whole recovery environment on a mocked AWS provider: no credentials, no resources.

mock_provider "aws" {
  override_during = plan

  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }

  mock_data "aws_availability_zones" {
    defaults = { names = ["ap-southeast-1a", "ap-southeast-1b", "ap-southeast-1c"] }
  }

  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }

  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }

  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0", insecure_value = "ami-0123456789abcdef0" }
  }

  mock_resource "aws_iam_role" {
    defaults = { arn = "arn:aws:iam::123456789012:role/bdr-recovery-mock" }
  }

  mock_resource "aws_instance" {
    defaults = { id = "i-0123456789abcdef0" }
  }

  mock_resource "aws_cloudwatch_log_group" {
    defaults = { arn = "arn:aws:logs:ap-southeast-1:123456789012:log-group:/bayanihandr/recovery/recovery" }
  }

  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::bayanihandr-backups-123456789012-ap-southeast-1" }
  }
}

run "standby_by_default_has_no_paid_compute" {
  command = plan

  assert {
    condition     = output.recovery_enabled == false && output.recovery_host_instance_id == null && output.ssm_session_command == null
    error_message = "With defaults, no recovery host may be planned."
  }

  assert {
    condition     = length(module.networking) == 0 && length(module.compute) == 0
    error_message = "With defaults, the VPC and compute modules must not be instantiated."
  }

  assert {
    condition     = output.backup_bucket_name == "bayanihandr-backups-123456789012-ap-southeast-1"
    error_message = "Bucket name must be derived from the account ID and region, got ${output.backup_bucket_name}."
  }

  assert {
    condition     = output.recovery_log_group_name == "/bayanihandr/recovery/recovery"
    error_message = "Unexpected log group name ${output.recovery_log_group_name}."
  }

  assert {
    condition     = output.budget_name == null && output.backup_writer_role_arn == null
    error_message = "Budget and backup-writer role are opt-in and must be absent by default."
  }
}

run "recovery_drill_adds_network_host_and_alarm" {
  command = plan

  variables {
    recovery_enabled  = true
    recovery_point_id = "20261104T070000Z"
  }

  assert {
    condition     = length(module.networking) == 1 && length(module.compute) == 1
    error_message = "A recovery must instantiate the networking and compute modules."
  }

  assert {
    condition     = output.recovery_host_instance_id == "i-0123456789abcdef0"
    error_message = "The recovery host instance ID must be exposed."
  }

  assert {
    condition     = output.ssm_session_command == "aws ssm start-session --region ap-southeast-1 --target i-0123456789abcdef0"
    error_message = "The SSM session command is wrong: ${coalesce(output.ssm_session_command, "null")}."
  }
}

run "opt_in_budget_and_backup_writer" {
  command = plan

  variables {
    budget_alert_email           = "ops@example.com"
    backup_writer_principal_arns = ["arn:aws:iam::123456789012:role/bdr-operator"]
  }

  assert {
    condition     = output.budget_name == "bdr-recovery-monthly-cost"
    error_message = "Setting an alert email must create the monthly budget."
  }

  assert {
    condition     = output.backup_writer_role_arn == "arn:aws:iam::123456789012:role/bdr-recovery-mock"
    error_message = "Trusted principals must create the backup-writer role."
  }
}

run "rejects_other_regions" {
  command = plan

  variables {
    aws_region = "us-east-1"
  }

  expect_failures = [var.aws_region]
}

run "rejects_large_instance_types" {
  command = plan

  variables {
    recovery_enabled = true
    instance_type    = "m5.4xlarge"
  }

  expect_failures = [var.instance_type]
}

run "rejects_malformed_recovery_points" {
  command = plan

  variables {
    recovery_enabled  = true
    recovery_point_id = "latest; rm -rf /"
  }

  expect_failures = [var.recovery_point_id]
}
