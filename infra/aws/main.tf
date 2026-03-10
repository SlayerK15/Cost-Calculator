terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket = "llm-platform-tfstate"
    key    = "platform/terraform.tfstate"
    region = "us-east-1"
  }
}

provider "aws" {
  region = var.region
}

# ── VPC ──
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  name = "llm-platform-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.region}a", "${var.region}b", "${var.region}c"]
  private_subnets = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
  public_subnets  = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = true
  enable_dns_hostnames = true

  tags = var.common_tags
}

# ── EKS ──
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = "llm-platform"
  cluster_version = "1.29"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  cluster_endpoint_public_access = true

  eks_managed_node_groups = {
    system = {
      instance_types = ["m5.large"]
      min_size       = 1
      max_size       = 3
      desired_size   = 2
    }

    gpu_a10g = {
      instance_types = [var.gpu_instance_type]
      min_size       = 0
      max_size       = var.max_gpu_nodes
      desired_size   = 0

      ami_type = "AL2_x86_64_GPU"

      labels = {
        "workload"  = "llm-inference"
        "gpu-type"  = "a10g"
      }

      taints = [{
        key    = "nvidia.com/gpu"
        value  = "true"
        effect = "NO_SCHEDULE"
      }]
    }
  }

  tags = var.common_tags
}

# ── RDS (PostgreSQL) ──
module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.0"

  identifier = "llm-platform-db"

  engine         = "postgres"
  engine_version = "16"
  instance_class = "db.t3.medium"

  allocated_storage = 20
  storage_type      = "gp3"

  db_name  = "llmplatform"
  username = "postgres"
  port     = 5432

  vpc_security_group_ids = [aws_security_group.rds.id]
  subnet_ids             = module.vpc.private_subnets

  family               = "postgres16"
  major_engine_version = "16"

  deletion_protection = false
  skip_final_snapshot = true

  tags = var.common_tags
}

resource "aws_security_group" "rds" {
  name_prefix = "llm-platform-rds-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
}

# ── ElastiCache (Redis) ──
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "llm-platform-redis"
  engine               = "redis"
  node_type            = "cache.t3.medium"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.redis.name
  security_group_ids   = [aws_security_group.redis.id]

  tags = var.common_tags
}

resource "aws_elasticache_subnet_group" "redis" {
  name       = "llm-platform-redis"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name_prefix = "llm-platform-redis-"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
}

# ── ECR ──
resource "aws_ecr_repository" "platform" {
  name                 = "llm-platform"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.common_tags
}

# ── S3 for model storage ──
resource "aws_s3_bucket" "models" {
  bucket        = "llm-platform-models-${var.region}"
  force_destroy = true
  tags          = var.common_tags
}

resource "aws_s3_bucket_server_side_encryption_configuration" "models" {
  bucket = aws_s3_bucket.models.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# ── Outputs ──
output "eks_cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "ecr_repository_url" {
  value = aws_ecr_repository.platform.repository_url
}

output "rds_endpoint" {
  value = module.rds.db_instance_endpoint
}

output "redis_endpoint" {
  value = aws_elasticache_cluster.redis.cache_nodes[0].address
}

output "model_bucket" {
  value = aws_s3_bucket.models.bucket
}
