variable "project_id" {
  description = "Explicit isolated dev project ID; the active gcloud project is never inherited."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid, explicit Google Cloud project ID."
  }
}

variable "bootstrap_project_id" {
  description = "Explicit reviewed bootstrap project ID; it must differ from the dev project."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.bootstrap_project_id))
    error_message = "bootstrap_project_id must be a valid explicit Google Cloud project ID."
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
  description = "Explicitly selected open billing account. Discovery currently found no eligible value."
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
  description = "Region selected after effective location-policy, quota, tier, and price checks."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]$", var.region))
    error_message = "region must be an explicit Google Cloud region."
  }
}

variable "image_pusher_service_account_email" {
  description = "Build-phase WIF identity; granted writer only on the dev Artifact Registry repository."
  type        = string
  nullable    = false

  validation {
    condition     = endswith(var.image_pusher_service_account_email, ".gserviceaccount.com")
    error_message = "image_pusher_service_account_email must be a service account email."
  }
}

variable "runtime_plan_service_account_email" {
  description = "Plan-phase WIF identity; read-only for Cloud Run plus remote-state object access."
  type        = string
  nullable    = false

  validation {
    condition     = endswith(var.runtime_plan_service_account_email, ".gserviceaccount.com")
    error_message = "runtime_plan_service_account_email must be a service account email."
  }
}

variable "runtime_deployer_service_account_email" {
  description = "Apply-phase WIF identity; exact Cloud Run operations, repository image read, and runtime-SA use."
  type        = string
  nullable    = false

  validation {
    condition = (
      endswith(var.runtime_deployer_service_account_email, ".gserviceaccount.com")
      && var.runtime_deployer_service_account_email != var.runtime_plan_service_account_email
      && var.runtime_deployer_service_account_email != var.image_pusher_service_account_email
      && var.runtime_plan_service_account_email != var.image_pusher_service_account_email
    )
    error_message = "All build, plan and deploy service-account emails must be valid and distinct."
  }
}

variable "github_repository_owner_id" {
  description = "Immutable GitHub owner ID reviewed in the bootstrap WIF configuration."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_owner_id))
    error_message = "github_repository_owner_id must be an immutable numeric GitHub owner ID."
  }
}

variable "github_repository_id" {
  description = "Immutable GitHub repository ID reviewed in the bootstrap WIF configuration."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_id))
    error_message = "github_repository_id must be an immutable numeric GitHub repository ID."
  }
}

variable "monthly_budget_usd" {
  type    = number
  default = 50
}

variable "notification_channels" {
  description = "Sensitive, versioned create/adopt configuration for Terraform-managed Monitoring email channels."
  type = list(object({
    schema_version        = string
    key                   = string
    provisioning_mode     = string
    project_id            = string
    display_name          = string
    email_address         = string
    existing_channel_name = optional(string)
    evidence_sha256       = optional(string)
    decision_reference    = optional(string)
    acknowledgement       = string
  }))
  nullable  = false
  sensitive = true

  validation {
    condition = (
      length(var.notification_channels) > 0
      && length(var.notification_channels) <= 5
      && length(distinct([
        for channel in var.notification_channels : channel.key
      ])) == length(var.notification_channels)
      && alltrue([
        for channel in var.notification_channels :
        channel.schema_version == "gcp-notification-channel.v1"
        && contains(["CREATE_NEW", "ADOPT_EXISTING"], channel.provisioning_mode)
        && channel.project_id == var.project_id
        && can(regex("^[a-z][a-z0-9_-]{1,30}[a-z0-9]$", channel.key))
        && can(regex("^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}[A-Za-z0-9]$", channel.display_name))
        && can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", channel.email_address))
        && (channel.evidence_sha256 == null || can(regex("^[0-9a-f]{64}$", channel.evidence_sha256)))
        && (channel.decision_reference == null || can(regex("^https://[^[:space:]]+$", channel.decision_reference)))
        && (
          channel.provisioning_mode == "CREATE_NEW" ? (
            channel.existing_channel_name == null
            && channel.acknowledgement == "I_ACKNOWLEDGE_TERRAFORM_WILL_CREATE_AND_MANAGE_THIS_EMAIL_CHANNEL"
            ) : (
            can(regex("^projects/${var.project_id}/notificationChannels/[0-9]+$", channel.existing_channel_name))
            && channel.evidence_sha256 != null
            && channel.decision_reference != null
            && channel.acknowledgement == "I_ACKNOWLEDGE_TERRAFORM_WILL_IMPORT_AND_MANAGE_THIS_VERIFIED_EMAIL_CHANNEL"
          )
        )
      ])
    )
    error_message = "Provide one to five distinct gcp-notification-channel.v1 CREATE_NEW or ADOPT_EXISTING records bound to this project; adopted channels require an exact channel name and reviewed evidence."
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
