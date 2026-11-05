terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Deliberately local state: this configuration creates the remote state bucket itself. Its state file is
  # tiny, holds no secrets, and is kept by the operator outside git (*.tfstate is git-ignored).
}
