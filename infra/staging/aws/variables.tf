variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "llm-platform"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "staging"
}

variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "ec2_instance_type" {
  description = "EC2 instance type for app server"
  type        = string
  default     = "t3.medium"
}

variable "ec2_key_name" {
  description = "SSH key pair name (must already exist in AWS)"
  type        = string
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
  default     = "llmplatform"
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "allowed_ssh_cidr" {
  description = "CIDR allowed to SSH (set to your IP, e.g. 1.2.3.4/32)"
  type        = string
  default     = "0.0.0.0/0"
}

variable "allowed_app_cidr" {
  description = "CIDR allowed to access the app (frontend/backend ports)"
  type        = string
  default     = "0.0.0.0/0"
}
