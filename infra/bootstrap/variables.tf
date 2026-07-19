variable "project_id" {
  description = "Explicit bootstrap project ID; never inferred from the active gcloud configuration."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid, explicit Google Cloud project ID."
  }
}

variable "create_project" {
  description = "Create the isolated bootstrap project when true; otherwise adopt the explicit project_id."
  type        = bool
  default     = false
}

variable "billing_account" {
  description = "Selected open billing account for project creation; null when adopting."
  type        = string
  default     = null
  nullable    = true
  sensitive   = true
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

variable "github_repository" {
  type     = string
  nullable = false
}

variable "github_allowed_ref" {
  type    = string
  default = "refs/heads/main"
}

variable "github_workflow_path" {
  type    = string
  default = ".github/workflows/deploy-dev.yml"
}

variable "labels" {
  type = map(string)
  default = {
    application = "ai-native-content-agency"
    environment = "bootstrap"
    managed_by  = "terraform"
  }
}
