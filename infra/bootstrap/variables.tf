variable "project_id" {
  description = "Explicit bootstrap project ID; never inferred from the active gcloud configuration."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid, explicit Google Cloud project ID."
  }
}

variable "project_provisioning_mode" {
  description = "Explicit project lifecycle: create a new project or import and manage a reviewed existing project."
  type        = string
  nullable    = false

  validation {
    condition     = contains(["CREATE_NEW", "ADOPT_EXISTING"], var.project_provisioning_mode)
    error_message = "project_provisioning_mode must be CREATE_NEW or ADOPT_EXISTING."
  }
}

variable "existing_project_adoption" {
  description = "Versioned acknowledgement bound to discovery evidence when ADOPT_EXISTING is selected."
  type = object({
    schema_version     = string
    project_id         = string
    evidence_sha256    = string
    decision_reference = string
    acknowledgement    = string
  })
  default  = null
  nullable = true

  validation {
    condition = var.existing_project_adoption == null ? true : (
      var.existing_project_adoption.schema_version == "gcp-project-adoption.v1"
      && can(regex("^[0-9a-f]{64}$", var.existing_project_adoption.evidence_sha256))
      && can(regex("^https://[^[:space:]]+$", var.existing_project_adoption.decision_reference))
      && var.existing_project_adoption.acknowledgement == "I_ACKNOWLEDGE_TERRAFORM_WILL_MANAGE_THIS_EXISTING_PROJECT"
    )
    error_message = "existing_project_adoption must use gcp-project-adoption.v1, bind SHA-256 evidence and an HTTPS decision reference, and carry the exact acknowledgement."
  }
}

variable "billing_account" {
  description = "Explicitly selected open billing account for the managed bootstrap project."
  type        = string
  nullable    = false
  sensitive   = true

  validation {
    condition     = can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account))
    error_message = "billing_account must be a selected Google Cloud billing account ID."
  }
}

variable "organization_id" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "folder_id" {
  type      = string
  default   = null
  nullable  = true
  sensitive = true
}

variable "region" {
  description = "Region selected only after effective location-policy and service availability checks."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]$", var.region))
    error_message = "region must be an explicit Google Cloud region such as us-central1."
  }
}

variable "state_bucket_name" {
  description = "Globally unique non-personal bucket name for encrypted Terraform state."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9._-]{10,61}[a-z0-9]$", var.state_bucket_name))
    error_message = "state_bucket_name must be a valid globally unique bucket name."
  }
}

variable "github_repository_owner" {
  type     = string
  nullable = false
}

variable "github_repository_owner_id" {
  description = "Immutable numeric GitHub owner ID verified against the OIDC claim."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_owner_id))
    error_message = "github_repository_owner_id must be an immutable numeric GitHub owner ID."
  }
}

variable "github_repository" {
  type     = string
  nullable = false
}

variable "github_repository_id" {
  description = "Immutable numeric GitHub repository ID verified against the OIDC claim."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_id))
    error_message = "github_repository_id must be an immutable numeric GitHub repository ID."
  }
}

variable "github_allowed_ref" {
  type    = string
  default = "refs/heads/main"
}

variable "github_workflow_path" {
  type    = string
  default = ".github/workflows/deploy-dev.yml"
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
