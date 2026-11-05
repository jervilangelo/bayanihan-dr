provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "BayanihanDR"
      Component = "terraform-state"
      ManagedBy = "Terraform"
    }
  }
}
