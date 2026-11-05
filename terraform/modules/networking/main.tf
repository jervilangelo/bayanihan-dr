# Minimal, isolated network for the temporary recovery host (blueprint §8.1, §8.4).
# One public subnet and an Internet Gateway for outbound HTTPS only. No NAT Gateway (cost), no inbound
# rules at all: operators reach the host through SSM Session Manager, which needs outbound 443 only.

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.name_prefix}-vpc"
  }
}

# Strip every rule from the VPC's default security group so nothing can use it by accident.
resource "aws_default_security_group" "main" {
  vpc_id  = aws_vpc.main.id
  ingress = []
  egress  = []

  tags = {
    Name = "${var.name_prefix}-default-locked"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-igw"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = var.public_subnet_cidr
  availability_zone       = var.availability_zone
  map_public_ip_on_launch = false # the instance opts in explicitly

  tags = {
    Name = "${var.name_prefix}-public"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.name_prefix}-public"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# Free gateway endpoint: backup downloads from S3 stay on the AWS network and avoid internet data charges.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_route_table.public.id]

  tags = {
    Name = "${var.name_prefix}-s3"
  }
}

resource "aws_security_group" "recovery_host" {
  name        = "${var.name_prefix}-recovery-host"
  description = "Recovery host: no inbound access; outbound HTTPS only (SSM, S3, package repositories)"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.name_prefix}-recovery-host"
  }
}

resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.recovery_host.id
  description       = "HTTPS to SSM, S3 and package repositories"
  ip_protocol       = "tcp"
  from_port         = 443
  to_port           = 443
  cidr_ipv4         = "0.0.0.0/0"
}
