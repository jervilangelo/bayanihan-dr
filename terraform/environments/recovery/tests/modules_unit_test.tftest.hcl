# Plan-only tests of each module's security and cost settings, on a mocked AWS provider.

mock_provider "aws" {
  override_during = plan

  mock_data "aws_iam_policy_document" {
    defaults = { json = "{\"Version\":\"2012-10-17\",\"Statement\":[]}" }
  }

  mock_data "aws_partition" {
    defaults = { partition = "aws" }
  }

  mock_data "aws_ssm_parameter" {
    defaults = { value = "ami-0123456789abcdef0", insecure_value = "ami-0123456789abcdef0" }
  }
}

# ---- compute ----

run "compute_host_is_hardened_and_cost_capped" {
  command = plan

  module {
    source = "../../modules/compute"
  }

  variables {
    name_prefix           = "bdr-test"
    region                = "ap-southeast-1"
    subnet_id             = "subnet-0123456789abcdef0"
    security_group_ids    = ["sg-0123456789abcdef0"]
    instance_profile_name = "bdr-test-recovery-host"
    backup_bucket_name    = "bayanihandr-backups-test"
    backup_prefix         = "backups/"
    log_group_name        = "/bayanihandr/test/recovery"
    recovery_point_id     = "20261104T070000Z"
    job_id                = "job-20261105T060000Z-a1b2c3"
    app_git_ref           = "f1f86cb8279e22092b2cd85553adae7d162420b2"
  }

  assert {
    condition     = aws_instance.recovery_host.metadata_options[0].http_tokens == "required" && aws_instance.recovery_host.metadata_options[0].http_put_response_hop_limit == 1
    error_message = "The host must require IMDSv2 with a hop limit of 1."
  }

  assert {
    condition     = aws_instance.recovery_host.root_block_device[0].encrypted && aws_instance.recovery_host.root_block_device[0].delete_on_termination
    error_message = "The root volume must be encrypted and deleted with the instance."
  }

  assert {
    condition     = aws_instance.recovery_host.root_block_device[0].volume_type == "gp3" && aws_instance.recovery_host.root_block_device[0].volume_size == 20
    error_message = "The root volume must be a 20 GiB gp3 volume by default."
  }

  assert {
    condition     = aws_instance.recovery_host.credit_specification[0].cpu_credits == "standard"
    error_message = "T3 burst credits must be capped (standard) to avoid surprise charges."
  }

  assert {
    condition     = aws_instance.recovery_host.instance_type == "t3.small" && aws_instance.recovery_host.instance_initiated_shutdown_behavior == "terminate"
    error_message = "Default must be t3.small, terminated (not stopped) on shutdown."
  }

  assert {
    condition     = aws_instance.recovery_host.ami == "ami-0123456789abcdef0" && aws_instance.recovery_host.associate_public_ip_address
    error_message = "The host must use the SSM-resolved AMI and a public IP for outbound access without NAT."
  }

  assert {
    condition     = aws_instance.recovery_host.tags["RecoveryPoint"] == "20261104T070000Z" && aws_instance.recovery_host.tags["JobId"] == "job-20261105T060000Z-a1b2c3"
    error_message = "The chosen recovery point must be recorded on the instance."
  }

  assert {
    condition = alltrue([
      for needle in ["BACKUP_ID='20261104T070000Z'", "BUCKET='bayanihandr-backups-test'", "JOB_ID='job-20261105T060000Z-a1b2c3'", "APP_REF='f1f86cb8279e22092b2cd85553adae7d162420b2'", "set -euo pipefail", "verify-checksum", "recovery-complete"] :
      strcontains(aws_instance.recovery_host.user_data, needle)
    ])
    error_message = "The bootstrap script must carry the recovery settings and fail fast."
  }
}

# ---- networking ----

run "network_allows_no_inbound_and_https_out_only" {
  command = plan

  module {
    source = "../../modules/networking"
  }

  variables {
    name_prefix       = "bdr-test"
    region            = "ap-southeast-1"
    availability_zone = "ap-southeast-1a"
  }

  assert {
    condition     = aws_vpc_security_group_egress_rule.https.from_port == 443 && aws_vpc_security_group_egress_rule.https.to_port == 443 && aws_vpc_security_group_egress_rule.https.ip_protocol == "tcp"
    error_message = "The only egress rule must be TCP 443."
  }

  assert {
    condition     = length(aws_default_security_group.main.ingress) == 0 && length(aws_default_security_group.main.egress) == 0
    error_message = "The VPC default security group must have no rules."
  }

  assert {
    condition     = aws_subnet.public.map_public_ip_on_launch == false
    error_message = "The subnet must not hand out public IPs automatically."
  }

  assert {
    condition     = aws_vpc_endpoint.s3.vpc_endpoint_type == "Gateway" && aws_vpc_endpoint.s3.service_name == "com.amazonaws.ap-southeast-1.s3"
    error_message = "S3 must be reached through a free gateway endpoint."
  }
}

# ---- storage ----

run "backup_bucket_is_private_encrypted_versioned" {
  command = plan

  module {
    source = "../../modules/storage"
  }

  variables {
    bucket_name = "bayanihandr-backups-test"
  }

  assert {
    condition     = aws_s3_bucket.backups.force_destroy == false
    error_message = "The backup bucket must not be deletable while it holds backups."
  }

  assert {
    condition = alltrue([
      aws_s3_bucket_public_access_block.backups.block_public_acls,
      aws_s3_bucket_public_access_block.backups.block_public_policy,
      aws_s3_bucket_public_access_block.backups.ignore_public_acls,
      aws_s3_bucket_public_access_block.backups.restrict_public_buckets,
    ])
    error_message = "All four public access blocks must be on."
  }

  assert {
    condition     = aws_s3_bucket_versioning.backups.versioning_configuration[0].status == "Enabled"
    error_message = "Versioning must be enabled."
  }

  assert {
    condition     = one([for r in aws_s3_bucket_server_side_encryption_configuration.backups.rule : r.apply_server_side_encryption_by_default[0].sse_algorithm]) == "AES256"
    error_message = "Default encryption must be SSE-S3 when no KMS key is given."
  }

  assert {
    condition     = aws_s3_bucket_ownership_controls.backups.rule[0].object_ownership == "BucketOwnerEnforced"
    error_message = "ACLs must be disabled."
  }

  assert {
    condition     = one([for s in data.aws_iam_policy_document.backups.statement : s.effect if s.sid == "DenyInsecureTransport"]) == "Deny"
    error_message = "The bucket policy must deny non-TLS access."
  }

  assert {
    condition     = one([for r in aws_s3_bucket_lifecycle_configuration.backups.rule : r.expiration[0].days if r.id == "expire-old-backups"]) == 30
    error_message = "Backups must expire after 30 days by default."
  }
}

run "backup_bucket_uses_kms_when_given_a_key" {
  command = plan

  module {
    source = "../../modules/storage"
  }

  variables {
    bucket_name = "bayanihandr-backups-test"
    kms_key_arn = "arn:aws:kms:ap-southeast-1:123456789012:key/00000000-0000-0000-0000-000000000000"
  }

  assert {
    condition     = one([for r in aws_s3_bucket_server_side_encryption_configuration.backups.rule : r.apply_server_side_encryption_by_default[0].sse_algorithm == "aws:kms" && r.bucket_key_enabled])
    error_message = "A KMS key must switch encryption to SSE-KMS with a bucket key."
  }
}

run "storage_rejects_invalid_bucket_names" {
  command = plan

  module {
    source = "../../modules/storage"
  }

  variables {
    bucket_name = "Not_A_Valid_Bucket"
  }

  expect_failures = [var.bucket_name]
}

# ---- identity ----

run "iam_grants_no_delete_and_writer_is_opt_in" {
  command = plan

  module {
    source = "../../modules/identity"
  }

  variables {
    name_prefix       = "bdr-test"
    backup_bucket_arn = "arn:aws:s3:::bayanihandr-backups-test"
    backup_prefix     = "backups/"
    log_group_arn     = "arn:aws:logs:ap-southeast-1:123456789012:log-group:/bayanihandr/test/recovery"
  }

  assert {
    condition     = length(aws_iam_role.backup_writer) == 0
    error_message = "The backup-writer role must not exist without trusted principals."
  }

  assert {
    condition = alltrue(flatten([
      for s in concat(data.aws_iam_policy_document.recovery_host.statement, data.aws_iam_policy_document.backup_writer.statement) : [
        for a in s.actions : !can(regex("(?i)delete|\\*", a))
      ]
    ]))
    error_message = "No policy may grant delete actions or wildcards."
  }

  assert {
    condition     = one([for s in data.aws_iam_policy_document.backup_writer.statement : s.actions]) == toset(["s3:PutObject"])
    error_message = "The backup writer may only upload."
  }

  assert {
    condition     = one([for s in data.aws_iam_policy_document.recovery_host.statement : s.resources if s.sid == "ReadBackups"]) == toset(["arn:aws:s3:::bayanihandr-backups-test/backups/*"])
    error_message = "The recovery host may read only the backup prefix."
  }

  assert {
    condition     = aws_iam_role_policy_attachment.recovery_host_ssm.policy_arn == "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
    error_message = "The host must be reachable through SSM, not SSH."
  }
}

run "identity_creates_writer_for_trusted_principals" {
  command = plan

  module {
    source = "../../modules/identity"
  }

  variables {
    name_prefix                  = "bdr-test"
    backup_bucket_arn            = "arn:aws:s3:::bayanihandr-backups-test"
    backup_prefix                = "backups/"
    log_group_arn                = "arn:aws:logs:ap-southeast-1:123456789012:log-group:/bayanihandr/test/recovery"
    backup_writer_principal_arns = ["arn:aws:iam::123456789012:role/bdr-operator"]
  }

  assert {
    condition     = length(aws_iam_role.backup_writer) == 1 && aws_iam_role.backup_writer[0].max_session_duration == 3600
    error_message = "Trusted principals must create a writer role with one-hour sessions."
  }
}

# ---- monitoring ----

run "monitoring_defaults_are_cheap" {
  command = plan

  module {
    source = "../../modules/monitoring"
  }

  variables {
    name_prefix = "bdr-test"
    environment = "test"
  }

  assert {
    condition     = aws_cloudwatch_log_group.recovery.retention_in_days == 7
    error_message = "Logs must be kept 7 days by default."
  }

  assert {
    condition     = length(aws_cloudwatch_metric_alarm.recovery_host_status) == 0 && length(aws_budgets_budget.monthly) == 0
    error_message = "No alarm or budget may exist unless requested."
  }
}

run "monitoring_rejects_long_log_retention" {
  command = plan

  module {
    source = "../../modules/monitoring"
  }

  variables {
    name_prefix        = "bdr-test"
    environment        = "test"
    log_retention_days = 365
  }

  expect_failures = [var.log_retention_days]
}
