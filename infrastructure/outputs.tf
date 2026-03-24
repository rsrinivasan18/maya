output "app_runner_url" {
  description = "MAYA live URL (HTTPS, free *.awsapprunner.com domain)"
  value       = "https://${aws_apprunner_service.maya_web.service_url}"
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint — use in DATABASE_URL secret"
  value       = aws_db_instance.maya.endpoint
}

output "ecr_repository_uri" {
  description = "ECR repository URI — use for docker push"
  value       = aws_ecr_repository.maya_web.repository_url
}

output "ecr_push_commands" {
  description = "Exact commands to push local maya-web:latest image to ECR"
  value = <<-EOT

    # Step 1 — authenticate Docker to ECR
    aws ecr get-login-password --region ${var.region} | \
      docker login --username AWS --password-stdin ${aws_ecr_repository.maya_web.repository_url}

    # Step 2 — tag local image
    docker tag maya-web:latest ${aws_ecr_repository.maya_web.repository_url}:latest

    # Step 3 — push
    docker push ${aws_ecr_repository.maya_web.repository_url}:latest

  EOT
}

output "secrets_update_commands" {
  description = "Commands to fill in real secret values after apply"
  value = <<-EOT

    # Replace REPLACE_ME with real values — run once after terraform apply:

    aws secretsmanager put-secret-value \
      --secret-id /maya/anthropic-api-key \
      --secret-string "YOUR_ANTHROPIC_KEY" \
      --region ${var.region}

    aws secretsmanager put-secret-value \
      --secret-id /maya/sarvam-api-key \
      --secret-string "YOUR_SARVAM_KEY" \
      --region ${var.region}

    aws secretsmanager put-secret-value \
      --secret-id /maya/sarvam-api-url \
      --secret-string "YOUR_SARVAM_URL" \
      --region ${var.region}

    aws secretsmanager put-secret-value \
      --secret-id /maya/database-url \
      --secret-string "postgresql://mayaadmin:PASSWORD@RDS_ENDPOINT/mayadb?sslmode=require" \
      --region ${var.region}

    aws secretsmanager put-secret-value \
      --secret-id /maya/connectivity-host \
      --secret-string "api.anthropic.com" \
      --region ${var.region}

    aws secretsmanager put-secret-value \
      --secret-id /maya/connectivity-port \
      --secret-string "443" \
      --region ${var.region}

  EOT
}
