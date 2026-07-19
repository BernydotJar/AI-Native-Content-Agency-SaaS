variable "project_id" {
  description = "Explicit isolated dev project ID; never inherited from gcloud."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be one explicit valid Google Cloud project ID."
  }
}

variable "bootstrap_project_id" {
  description = "Exact reviewed bootstrap project ID; it must differ from the dev project."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.bootstrap_project_id))
    error_message = "bootstrap_project_id must be one explicit valid Google Cloud project ID."
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

variable "foundation_project_provenance_sha256" {
  description = "Exact reviewed project provenance digest exported by the dev foundation."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.foundation_project_provenance_sha256))
    error_message = "foundation_project_provenance_sha256 must be a lowercase SHA-256 digest."
  }
}

variable "foundation_notification_channel_provenance_sha256" {
  description = "Exact reviewed notification-channel create/adopt provenance digest exported by the dev foundation."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[0-9a-f]{64}$", var.foundation_notification_channel_provenance_sha256))
    error_message = "foundation_notification_channel_provenance_sha256 must be a lowercase SHA-256 digest."
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

variable "github_repository_owner_id" {
  description = "Immutable GitHub owner ID bound by the reviewed bootstrap WIF and dev foundation."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_owner_id))
    error_message = "github_repository_owner_id must be an immutable numeric GitHub owner ID."
  }
}

variable "github_repository_id" {
  description = "Immutable GitHub repository ID bound by the reviewed bootstrap WIF and dev foundation."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_id))
    error_message = "github_repository_id must be an immutable numeric GitHub repository ID."
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
  description = "Exact source-reviewed Cloud SQL Auth Proxy repository, release and digest."
  type        = string
  default     = "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.2@sha256:fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"

  validation {
    condition     = var.cloud_sql_proxy_image == "gcr.io/cloud-sql-connectors/cloud-sql-proxy:2.18.2@sha256:fc224915ef435afeb5b2a9421260a0d31986d5c8b7c7f5783c7f5d5885700cd2"
    error_message = "cloud_sql_proxy_image must equal the exact source-reviewed proxy release and digest."
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

variable "additional_labels" {
  description = "Optional non-reserved labels. application, environment and managed_by are enforced by the root."
  type        = map(string)
  default     = {}

  validation {
    condition = length(setintersection(
      toset(keys(var.additional_labels)),
      toset(["application", "environment", "managed_by"]),
    )) == 0
    error_message = "additional_labels cannot override application, environment or managed_by."
  }
}
