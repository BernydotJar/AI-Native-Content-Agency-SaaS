variable "project_id" {
  type     = string
  nullable = false
}

variable "region" {
  type     = string
  nullable = false
}

variable "service_name" {
  type    = string
  default = "agency-control-plane-dev"
}

variable "container_image" {
  description = "Immutable application image reference. Tags are rejected."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.container_image))
    error_message = "container_image must be an immutable sha256 digest reference."
  }
}

variable "cloud_sql_proxy_image" {
  description = "Exact source-reviewed Cloud SQL Auth Proxy repository, release and digest."
  type        = string
  nullable    = false

  validation {
    condition     = var.cloud_sql_proxy_image == "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.2@sha256:fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"
    error_message = "cloud_sql_proxy_image must equal the exact source-reviewed proxy release and digest."
  }
}

variable "runtime_service_account_email" {
  type     = string
  nullable = false
}

variable "cloud_sql_connection_name" {
  type     = string
  nullable = false
}

variable "database_name" {
  type     = string
  nullable = false
}

variable "database_user" {
  type     = string
  nullable = false
}

variable "cors_origins" {
  type    = list(string)
  default = ["http://localhost:8080"]

  validation {
    condition     = length(var.cors_origins) > 0 && !contains(var.cors_origins, "*")
    error_message = "cors_origins must be explicit and cannot contain a wildcard."
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
