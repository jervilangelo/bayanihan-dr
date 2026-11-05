# Copy to backend.hcl (git-ignored) and fill in after the state bucket exists (terraform/bootstrap).
#   terraform init -backend-config=backend.hcl
bucket       = "bayanihandr-tfstate-<account-id>-ap-southeast-1"
key          = "recovery/terraform.tfstate"
region       = "ap-southeast-1"
encrypt      = true
use_lockfile = true # S3 native locking (Terraform 1.10+); no DynamoDB table
