terraform {
  # 1.10+ for S3 native state locking (use_lockfile), which avoids a DynamoDB lock table.
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Partial configuration: real values live in backend.hcl (git-ignored), copied from backend.example.hcl
  # after the state bucket is bootstrapped (terraform/bootstrap, Phase 5).
  #   terraform init -backend-config=backend.hcl
  backend "s3" {}
}
