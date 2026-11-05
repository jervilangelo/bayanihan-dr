variable "availability_zone" {
  description = "Availability zone for the single public subnet"
  type        = string
}

variable "name_prefix" {
  description = "Prefix for resource names, for example bdr-recovery"
  type        = string
}

variable "public_subnet_cidr" {
  description = "CIDR block of the public subnet; must sit inside vpc_cidr"
  type        = string
  default     = "10.42.1.0/24"

  validation {
    condition     = can(cidrnetmask(var.public_subnet_cidr))
    error_message = "public_subnet_cidr must be a valid IPv4 CIDR block."
  }
}

variable "region" {
  description = "AWS region, used for the S3 gateway endpoint service name"
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block of the recovery VPC"
  type        = string
  default     = "10.42.0.0/16"

  validation {
    condition     = can(cidrnetmask(var.vpc_cidr))
    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}
