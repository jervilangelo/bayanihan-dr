provider "aws" {
  region = var.aws_region

  # Credentials come from the operator's short-lived SSO session (AWS_PROFILE), never from this code.

  default_tags {
    tags = local.common_tags
  }
}
