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
  description = "Pinned Cloud SQL Auth Proxy image with automatic IAM database authentication."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[^[:space:]]+@sha256:[0-9a-f]{64}$", var.cloud_sql_proxy_image))
    error_message = "cloud_sql_proxy_image must be pinned by sha256 digest."
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

variable "invoker_members" {
  description = "Explicit authenticated principals only; no public principals are accepted."
  type        = set(string)
  default     = []

  validation {
    condition = alltrue([
      for member in var.invoker_members :
      member != "allUsers" && member != "allAuthenticatedUsers"
    ])
    error_message = "Public Cloud Run invoker members are forbidden."
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
