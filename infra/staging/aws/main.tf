terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

locals {
  name_prefix = "${var.project_name}-${var.environment}"
}

# ═══════════════════════════════════════════════════════
# Secrets — generated and stored in AWS Secrets Manager
# ═══════════════════════════════════════════════════════

resource "random_password" "db_password" {
  length  = 32
  special = false # RDS doesn't like some special chars
}

resource "random_password" "secret_key" {
  length  = 64
  special = false
}

resource "random_password" "n8n_password" {
  length  = 24
  special = false
}

resource "random_password" "n8n_callback_secret" {
  length  = 32
  special = false
}

resource "random_password" "credential_encryption_key" {
  length  = 64
  special = false
}

resource "random_password" "redis_auth_token" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "app_secrets" {
  name                    = "${local.name_prefix}/app-secrets"
  description             = "LLM Platform staging secrets"
  recovery_window_in_days = 0 # Staging — allow immediate deletion
}

resource "aws_secretsmanager_secret_version" "app_secrets" {
  secret_id = aws_secretsmanager_secret.app_secrets.id
  secret_string = jsonencode({
    SECRET_KEY                = random_password.secret_key.result
    POSTGRES_PASSWORD         = random_password.db_password.result
    REDIS_AUTH_TOKEN          = random_password.redis_auth_token.result
    N8N_PASSWORD              = random_password.n8n_password.result
    N8N_CALLBACK_SECRET       = random_password.n8n_callback_secret.result
    CREDENTIAL_ENCRYPTION_KEY = random_password.credential_encryption_key.result
    DATABASE_URL              = "postgresql+asyncpg://${var.db_name}:${random_password.db_password.result}@${aws_db_instance.postgres.endpoint}/${var.db_name}"
    DATABASE_URL_SYNC         = "postgresql://${var.db_name}:${random_password.db_password.result}@${aws_db_instance.postgres.endpoint}/${var.db_name}"
    REDIS_URL                 = "redis://:${random_password.redis_auth_token.result}@${aws_elasticache_replication_group.redis.primary_endpoint_address}:6379/0"
  })
}

# ═══════════════════════════════════════════════════════
# Networking — VPC, Subnets, Internet Gateway
# ═══════════════════════════════════════════════════════

resource "aws_vpc" "main" {
  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { Name = "${local.name_prefix}-vpc" }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = { Name = "${local.name_prefix}-igw" }
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 1)
  availability_zone       = "${var.region}a"
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.name_prefix}-public-a" }
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, 2)
  availability_zone       = "${var.region}b"
  map_public_ip_on_launch = true
  tags                    = { Name = "${local.name_prefix}-public-b" }
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 10)
  availability_zone = "${var.region}a"
  tags              = { Name = "${local.name_prefix}-private-a" }
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, 11)
  availability_zone = "${var.region}b"
  tags              = { Name = "${local.name_prefix}-private-b" }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
  tags = { Name = "${local.name_prefix}-public-rt" }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

# ═══════════════════════════════════════════════════════
# Security Groups
# ═══════════════════════════════════════════════════════

resource "aws_security_group" "ec2" {
  name_prefix = "${local.name_prefix}-ec2-"
  vpc_id      = aws_vpc.main.id
  description = "App server security group"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.allowed_ssh_cidr]
  }

  ingress {
    description = "Frontend"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_app_cidr]
  }

  ingress {
    description = "Backend API"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = [var.allowed_app_cidr]
  }

  ingress {
    description = "n8n"
    from_port   = 5678
    to_port     = 5678
    protocol    = "tcp"
    cidr_blocks = [var.allowed_app_cidr]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-ec2-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.name_prefix}-rds-"
  vpc_id      = aws_vpc.main.id
  description = "RDS PostgreSQL — only from EC2"

  ingress {
    description     = "Postgres from EC2"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  tags = { Name = "${local.name_prefix}-rds-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name_prefix}-redis-"
  vpc_id      = aws_vpc.main.id
  description = "ElastiCache Redis — only from EC2"

  ingress {
    description     = "Redis from EC2"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.ec2.id]
  }

  tags = { Name = "${local.name_prefix}-redis-sg" }

  lifecycle {
    create_before_destroy = true
  }
}

# ═══════════════════════════════════════════════════════
# RDS PostgreSQL
# ═══════════════════════════════════════════════════════

resource "aws_db_subnet_group" "main" {
  name       = "${local.name_prefix}-db-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  tags       = { Name = "${local.name_prefix}-db-subnet" }
}

resource "aws_db_instance" "postgres" {
  identifier     = "${local.name_prefix}-postgres"
  engine         = "postgres"
  engine_version = "16.4"
  instance_class = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp3"
  storage_encrypted     = true

  db_name  = var.db_name
  username = var.db_name
  password = random_password.db_password.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  multi_az            = false # Staging — single AZ
  publicly_accessible = false
  skip_final_snapshot  = true # Staging — no snapshot on destroy

  backup_retention_period = 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  parameter_group_name = aws_db_parameter_group.postgres.name

  tags = { Name = "${local.name_prefix}-postgres" }
}

resource "aws_db_parameter_group" "postgres" {
  family = "postgres16"
  name   = "${local.name_prefix}-pg-params"

  parameter {
    name  = "log_connections"
    value = "1"
  }

  parameter {
    name  = "log_disconnections"
    value = "1"
  }

  tags = { Name = "${local.name_prefix}-pg-params" }
}

# ═══════════════════════════════════════════════════════
# ElastiCache Redis
# ═══════════════════════════════════════════════════════

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-subnet"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
}

resource "aws_elasticache_replication_group" "redis" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "LLM Platform staging Redis"

  engine               = "redis"
  engine_version       = "7.1"
  node_type            = var.redis_node_type
  num_cache_clusters   = 1           # Staging — single node
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = random_password.redis_auth_token.result

  automatic_failover_enabled = false # Staging — no failover
  multi_az_enabled           = false

  snapshot_retention_limit = 0 # Staging — no snapshots

  tags = { Name = "${local.name_prefix}-redis" }
}

# ═══════════════════════════════════════════════════════
# EC2 Instance — App Server
# ═══════════════════════════════════════════════════════

resource "aws_iam_role" "ec2" {
  name = "${local.name_prefix}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "ec2.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy" "ec2_secrets" {
  name = "${local.name_prefix}-secrets-access"
  role = aws_iam_role.ec2.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = [aws_secretsmanager_secret.app_secrets.arn]
      }
    ]
  })
}

resource "aws_iam_instance_profile" "ec2" {
  name = "${local.name_prefix}-ec2-profile"
  role = aws_iam_role.ec2.name
}

data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"] # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

resource "aws_instance" "app" {
  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.ec2_instance_type
  key_name               = var.ec2_key_name
  subnet_id              = aws_subnet.public_a.id
  vpc_security_group_ids = [aws_security_group.ec2.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2.name

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    secret_arn         = aws_secretsmanager_secret.app_secrets.arn
    aws_region         = var.region
    db_host            = aws_db_instance.postgres.address
    db_port            = aws_db_instance.postgres.port
    db_name            = var.db_name
    redis_host         = aws_elasticache_replication_group.redis.primary_endpoint_address
    redis_port         = 6379
    project_name       = var.project_name
    environment        = var.environment
  }))

  tags = { Name = "${local.name_prefix}-app" }

  depends_on = [
    aws_db_instance.postgres,
    aws_elasticache_replication_group.redis,
    aws_secretsmanager_secret_version.app_secrets,
  ]
}

resource "aws_eip" "app" {
  instance = aws_instance.app.id
  domain   = "vpc"
  tags     = { Name = "${local.name_prefix}-eip" }
}
