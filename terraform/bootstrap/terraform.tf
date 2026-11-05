terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }

  # Chicken-and-egg: the first apply runs with local state (comment out this block), because this
  # configuration creates the state bucket. The state is then migrated into the bucket it created, so no
  # recovery step depends on the operator's laptop surviving the disaster:
  #   terraform init -migrate-state -backend-config=../environments/recovery/backend.hcl -backend-config="key=bootstrap/terraform.tfstate"
  backend "s3" {}
}
