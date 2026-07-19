variable "project_id" {
  type     = string
  nullable = false
}

variable "region" {
  type     = string
  nullable = false
}

variable "instance_name" {
  type    = string
  default = "agency-postgres-dev"
}

variable "database_name" {
  type    = string
  default = "agency"
}

variable "runtime_service_account_email" {
  description = "Cloud Run service account used as the PostgreSQL IAM database principal."
  type        = string
  nullable    = false

  validation {
    condition     = endswith(var.runtime_service_account_email, ".gserviceaccount.com")
    error_message = "runtime_service_account_email must be a Google service account email."
  }
}

variable "tier" {
  description = "Small shared-core dev tier; verify availability and price in the selected region before apply."
  type        = string
  default     = "db-f1-micro"
}

variable "disk_size_gb" {
  type    = number
  default = 10

  validation {
    condition     = var.disk_size_gb >= 10 && var.disk_size_gb <= 20
    error_message = "Dev disk size must remain between 10 and 20 GiB."
  }
}

variable "disk_autoresize_limit_gb" {
  type    = number
  default = 20

  validation {
    condition     = var.disk_autoresize_limit_gb >= 10 && var.disk_autoresize_limit_gb <= 50
    error_message = "Dev disk autoresize limit must remain between 10 and 50 GiB."
  }
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "labels" {
  type    = map(string)
  default = {}
}
