variable "region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "gpu_instance_type" {
  description = "GPU instance type for inference nodes"
  type        = string
  default     = "g5.xlarge"
}

variable "max_gpu_nodes" {
  description = "Maximum number of GPU nodes in the cluster"
  type        = number
  default     = 10
}

variable "common_tags" {
  description = "Common tags for all resources"
  type        = map(string)
  default = {
    Project     = "llm-platform"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}
