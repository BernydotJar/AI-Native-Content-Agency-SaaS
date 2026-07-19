variable "project_id" {
  description = "Explicit isolated dev project ID; never inherited from gcloud."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be one explicit valid Google Cloud project ID."
  }
}

variable "region" {
  type     = string
  nullable = false

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]$", var.region))
    error_message = "region must be an explicit Google Cloud region."
  }
}

variable "state_bucket_name" {
  description = "Exact bootstrap state bucket used by both this backend and foundation-state reads."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{10,61}[a-z0-9]$", var.state_bucket_name))
    error_message = "state_bucket_name must be an explicit valid bucket name."
  }
}

variable "runtime_deployer_service_account_email" {
  description = "Apply-phase WIF identity already authorized by the separately reviewed dev foundation."
  type        = string
  nullable    = false

  validation {
    condition     = endswith(var.runtime_deployer_service_account_email, ".gserviceaccount.com")
    error_message = "runtime_deployer_service_account_email must be a service-account email."
  }
}

variable "container_image" {
  description = "Immutable combined SPA/API image digest."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be pinned by sha256 digest."
  }
}

variable "cloud_sql_proxy_image" {
  description = "Immutable official Cloud SQL Auth Proxy image digest."
  type        = string
  default     = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.2@sha256:fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.cloud_sql_proxy_image))
    error_message = "cloud_sql_proxy_image must be pinned by sha256 digest."
  }
}

variable "cors_origins" {
  type    = list(string)
  default = ["http://localhost:8080"]

  validation {
    condition     = length(var.cors_origins) > 0 && !contains(var.cors_origins, "*")
    error_message = "cors_origins must be explicit and cannot contain a wildcard."
  }
}

variable "labels" {
  type = map(string)
  default = {
    application = "ai-native-content-agency"
    environment = "dev"
    managed_by  = "terraform"
  }
}
