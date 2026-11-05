# Temporary recovery host (blueprint §8.1, §10). Small, encrypted, IMDSv2-only, reachable only through SSM.
# It exists only during an approved recovery drill; the environment's recovery_enabled flag removes it.

data "aws_ssm_parameter" "ami" {
  name = var.ami_ssm_parameter
}

resource "aws_instance" "recovery_host" {
  ami                                  = data.aws_ssm_parameter.ami.insecure_value
  instance_type                        = var.instance_type
  subnet_id                            = var.subnet_id
  vpc_security_group_ids               = var.security_group_ids
  iam_instance_profile                 = var.instance_profile_name
  associate_public_ip_address          = true # outbound internet without a NAT Gateway
  instance_initiated_shutdown_behavior = "terminate"
  monitoring                           = false # detailed monitoring is billed; 5-minute metrics suffice

  user_data = templatefile("${path.module}/templates/bootstrap.sh.tftpl", {
    app_git_ref       = var.app_git_ref
    app_repo_url      = var.app_repo_url
    backup_bucket     = var.backup_bucket_name
    backup_prefix     = var.backup_prefix
    job_id            = var.job_id
    log_group_name    = var.log_group_name
    recovery_point_id = var.recovery_point_id
    region            = var.region
  })
  user_data_replace_on_change = true

  # T3 defaults to "unlimited" burst credits, which can add charges. Standard caps the cost.
  credit_specification {
    cpu_credits = "standard"
  }

  metadata_options {
    http_endpoint               = "enabled"
    http_tokens                 = "required" # IMDSv2 only
    http_put_response_hop_limit = 1          # containers cannot reach instance credentials
  }

  root_block_device {
    volume_type           = "gp3"
    volume_size           = var.root_volume_size_gb
    encrypted             = true
    delete_on_termination = true # no orphaned, still-billed volumes after teardown
  }

  tags = {
    Name          = "${var.name_prefix}-recovery-host"
    RecoveryPoint = var.recovery_point_id
    JobId         = var.job_id
  }

  lifecycle {
    # A newer AMI published mid-drill must not replace a host that is already restoring data.
    ignore_changes = [ami]
  }
}
