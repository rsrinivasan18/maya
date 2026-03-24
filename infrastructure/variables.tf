variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-southeast-1"
}

variable "db_password" {
  description = "Master password for RDS PostgreSQL (mayaadmin user). Min 8 chars."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.db_password) >= 8
    error_message = "db_password must be at least 8 characters."
  }
}
