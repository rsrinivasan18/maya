terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

# ── Locals ────────────────────────────────────────────────────────────────────

locals {
  tags = {
    Project     = "maya"
    Environment = "production"
    Owner       = "srinivasan"
    ManagedBy   = "terraform"
    CostCenter  = "maya-personal"
  }

  secret_keys = [
    "anthropic-api-key",
    "sarvam-api-key",
    "sarvam-api-url",
    "database-url",
    "connectivity-host",
    "connectivity-port",
  ]
}

# ── Data sources ──────────────────────────────────────────────────────────────

data "aws_caller_identity" "current" {}

# Default VPC — no custom VPC created
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ── ECR Repository ────────────────────────────────────────────────────────────
# Push image here before running terraform apply for App Runner.
# Command: see outputs.tf → ecr_push_commands

resource "aws_ecr_repository" "maya_web" {
  name                 = "maya-web"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = local.tags
}

resource "aws_ecr_lifecycle_policy" "maya_web" {
  repository = aws_ecr_repository.maya_web.name

  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep last 5 images"
      selection = {
        tagStatus   = "any"
        countType   = "imageCountMoreThan"
        countNumber = 5
      }
      action = { type = "expire" }
    }]
  })
}

# ── RDS Security Group ────────────────────────────────────────────────────────
# App Runner does not have fixed outbound IPs (no VPC connector used).
# PubliclyAccessible = true + rds.force_ssl = 1 enforces encrypted connections.
# Restrict to 0.0.0.0/0 at the SG level; SSL is the real security boundary.
# To further restrict: add a VPC connector and set cidr_blocks to VPC CIDR only.

resource "aws_security_group" "rds" {
  name        = "maya-rds-sg"
  description = "PostgreSQL access for MAYA - SSL enforced at DB level"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "PostgreSQL SSL required rds.force_ssl=1"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

# ── RDS Parameter Group — SSL required ────────────────────────────────────────

resource "aws_db_parameter_group" "maya" {
  name   = "maya-pg15-ssl"
  family = "postgres15"

  parameter {
    name         = "rds.force_ssl"
    value        = "1"
    apply_method = "immediate"
  }

  tags = local.tags
}

# ── RDS Subnet Group ──────────────────────────────────────────────────────────

resource "aws_db_subnet_group" "maya" {
  name       = "maya-db-subnet-group"
  subnet_ids = data.aws_subnets.default.ids
  tags       = local.tags
}

# ── RDS PostgreSQL ────────────────────────────────────────────────────────────

resource "aws_db_instance" "maya" {
  identifier     = "maya-db"
  engine         = "postgres"
  engine_version = "15"
  instance_class = "db.t3.micro"

  allocated_storage     = 20
  max_allocated_storage = 50
  storage_type          = "gp2"
  storage_encrypted     = true

  db_name  = "mayadb"
  username = "mayaadmin"
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.maya.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.maya.name

  publicly_accessible         = true
  auto_minor_version_upgrade  = true
  backup_retention_period     = 7
  deletion_protection         = false
  skip_final_snapshot         = false
  final_snapshot_identifier   = "maya-db-final-snapshot"

  tags = local.tags
}

# ── Secrets Manager ───────────────────────────────────────────────────────────
# All secrets created with placeholder "REPLACE_ME".
# Update real values via AWS Console or CLI after apply — never in code.

# Data sources: fetch exact ARNs (including random suffix) for App Runner injection
data "aws_secretsmanager_secret" "maya" {
  for_each   = toset(local.secret_keys)
  name       = "/maya/${each.key}"
  depends_on = [aws_secretsmanager_secret.maya]
}

resource "aws_secretsmanager_secret" "maya" {
  for_each = toset(local.secret_keys)
  name     = "/maya/${each.key}"
  tags     = local.tags
}

resource "aws_secretsmanager_secret_version" "maya" {
  for_each      = toset(local.secret_keys)
  secret_id     = aws_secretsmanager_secret.maya[each.key].id
  secret_string = "REPLACE_ME"

  lifecycle {
    # Prevent Terraform from overwriting real values set via Console/CLI
    ignore_changes = [secret_string]
  }
}

# ── IAM: App Runner Access Role (ECR pull at build time) ─────────────────────

resource "aws_iam_role" "apprunner_access" {
  name = "maya-apprunner-access-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "build.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "apprunner_ecr" {
  role       = aws_iam_role.apprunner_access.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# ── IAM: App Runner Instance Role (runtime — secrets + logs) ─────────────────

resource "aws_iam_role" "apprunner_instance" {
  name = "maya-apprunner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "tasks.apprunner.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "apprunner_instance" {
  name = "maya-apprunner-instance-policy"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "SecretsManagerRead"
        Effect = "Allow"
        Action = ["secretsmanager:GetSecretValue"]
        Resource = "arn:aws:secretsmanager:${var.region}:${data.aws_caller_identity.current.account_id}:secret:/maya/*"
      },
      {
        Sid    = "CloudWatchLogsWrite"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.region}:${data.aws_caller_identity.current.account_id}:log-group:/aws/apprunner/*"
      }
    ]
  })
}

# ── App Runner Service ────────────────────────────────────────────────────────
# IMPORTANT: Push an image to ECR before running terraform apply.
# App Runner will fail to create if ECR repo is empty.
# See outputs.tf → ecr_push_commands for the exact docker push commands.

resource "aws_apprunner_service" "maya_web" {
  service_name = "maya-web"

  source_configuration {
    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_access.arn
    }

    image_repository {
      image_identifier      = "${aws_ecr_repository.maya_web.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"

        # Secrets injected as env vars at runtime — exact ARNs from data sources
        runtime_environment_secrets = {
          ANTHROPIC_API_KEY      = data.aws_secretsmanager_secret.maya["anthropic-api-key"].arn
          SARVAM_API_KEY         = data.aws_secretsmanager_secret.maya["sarvam-api-key"].arn
          SARVAM_API_URL         = data.aws_secretsmanager_secret.maya["sarvam-api-url"].arn
          DATABASE_URL           = data.aws_secretsmanager_secret.maya["database-url"].arn
          MAYA_CONNECTIVITY_HOST = data.aws_secretsmanager_secret.maya["connectivity-host"].arn
          MAYA_CONNECTIVITY_PORT = data.aws_secretsmanager_secret.maya["connectivity-port"].arn
        }
      }
    }

    auto_deployments_enabled = false
  }

  instance_configuration {
    cpu               = "256"   # 0.25 vCPU
    memory            = "512"   # 0.5 GB
    instance_role_arn = aws_iam_role.apprunner_instance.arn
  }

  # depends_on ensures IAM role + inline policy are fully propagated before
  # App Runner validates permissions at service creation time.
  # Without this, Terraform creates the service while the policy is still
  # propagating — App Runner's permission check fails → CREATE_FAILED.
  depends_on = [
    aws_iam_role_policy.apprunner_instance,
    aws_iam_role_policy_attachment.apprunner_ecr,
  ]

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 20
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = local.tags
}
