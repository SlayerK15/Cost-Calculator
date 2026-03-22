output "app_public_ip" {
  description = "Public IP of the app server"
  value       = aws_eip.app.public_ip
}

output "frontend_url" {
  description = "Frontend URL"
  value       = "http://${aws_eip.app.public_ip}:3000"
}

output "backend_url" {
  description = "Backend API URL"
  value       = "http://${aws_eip.app.public_ip}:8000"
}

output "n8n_url" {
  description = "n8n workflow URL"
  value       = "http://${aws_eip.app.public_ip}:5678"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.endpoint
  sensitive   = false
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_replication_group.redis.primary_endpoint_address
  sensitive   = false
}

output "secrets_manager_arn" {
  description = "AWS Secrets Manager ARN"
  value       = aws_secretsmanager_secret.app_secrets.arn
}

output "ssh_command" {
  description = "SSH command to connect to the app server"
  value       = "ssh -i ~/.ssh/${var.ec2_key_name}.pem ubuntu@${aws_eip.app.public_ip}"
}

output "deploy_command" {
  description = "Command to deploy after rsync"
  value       = "rsync -az --exclude='.next' --exclude='node_modules' --exclude='__pycache__' --exclude='.git' --exclude='*.db' --exclude='.env' ./ ubuntu@${aws_eip.app.public_ip}:~/llm-platform/ && ssh ubuntu@${aws_eip.app.public_ip} 'cd ~/llm-platform && docker compose -f docker-compose.staging-aws.yml up -d --build'"
}

output "teardown_warning" {
  description = "How to destroy staging"
  value       = "Run: terraform destroy -var ec2_key_name=${var.ec2_key_name}"
}

output "estimated_monthly_cost" {
  description = "Estimated monthly cost for staging"
  value       = "~$45-55/mo (EC2 t3.medium ~$30 + RDS db.t3.micro ~$13 + ElastiCache cache.t3.micro ~$12)"
}
