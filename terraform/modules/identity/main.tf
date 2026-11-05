# Least-privilege IAM (blueprint §8.1, §11). No IAM users and no access keys: the recovery host uses an
# instance role, and the on-premises backup uploader assumes a role from an existing short-lived identity.

data "aws_partition" "current" {}

locals {
  backup_objects_arn = "${var.backup_bucket_arn}/${var.backup_prefix}*"
}

# ---- recovery host (EC2 instance role) ----

data "aws_iam_policy_document" "ec2_trust" {
  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "recovery_host" {
  name                 = "${var.name_prefix}-recovery-host"
  description          = "BayanihanDR recovery host: read backups, write its own logs, SSM access"
  assume_role_policy   = data.aws_iam_policy_document.ec2_trust.json
  max_session_duration = 3600
}

# SSM Session Manager instead of SSH: no inbound ports, no key pairs, every session audited by AWS.
resource "aws_iam_role_policy_attachment" "recovery_host_ssm" {
  role       = aws_iam_role.recovery_host.name
  policy_arn = "arn:${data.aws_partition.current.partition}:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "recovery_host" {
  statement {
    sid       = "ListBackupPrefix"
    actions   = ["s3:ListBucket"]
    resources = [var.backup_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["${var.backup_prefix}*"]
    }
  }

  statement {
    sid       = "ReadBackups"
    actions   = ["s3:GetObject", "s3:GetObjectVersion"]
    resources = [local.backup_objects_arn]
  }

  statement {
    sid       = "WriteRecoveryLogs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"]
    resources = ["${var.log_group_arn}:*"]
  }
}

resource "aws_iam_role_policy" "recovery_host" {
  name   = "read-backups-write-logs"
  role   = aws_iam_role.recovery_host.id
  policy = data.aws_iam_policy_document.recovery_host.json
}

resource "aws_iam_instance_profile" "recovery_host" {
  name = "${var.name_prefix}-recovery-host"
  role = aws_iam_role.recovery_host.name
}

# ---- on-premises backup uploader (optional) ----
# Created only when trusted principals are given (Phase 5 decides which). It can add backups but cannot
# read, list or delete them; with bucket versioning an overwrite keeps the previous version, so a
# compromised office server cannot destroy the off-site copies.

data "aws_iam_policy_document" "backup_writer_trust" {
  count = length(var.backup_writer_principal_arns) > 0 ? 1 : 0

  statement {
    actions = ["sts:AssumeRole"]

    principals {
      type        = "AWS"
      identifiers = var.backup_writer_principal_arns
    }
  }
}

resource "aws_iam_role" "backup_writer" {
  count = length(var.backup_writer_principal_arns) > 0 ? 1 : 0

  name                 = "${var.name_prefix}-backup-writer"
  description          = "BayanihanDR backup engine: upload new backups only"
  assume_role_policy   = data.aws_iam_policy_document.backup_writer_trust[0].json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "backup_writer" {
  statement {
    sid       = "UploadBackups"
    actions   = ["s3:PutObject"]
    resources = [local.backup_objects_arn]
  }
}

resource "aws_iam_role_policy" "backup_writer" {
  count = length(var.backup_writer_principal_arns) > 0 ? 1 : 0

  name   = "upload-backups"
  role   = aws_iam_role.backup_writer[0].id
  policy = data.aws_iam_policy_document.backup_writer.json
}
