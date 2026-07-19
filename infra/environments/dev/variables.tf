variable "project_id" {
  description = "Explicit isolated dev project ID; the active gcloud project is never inherited."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid, explicit Google Cloud project ID."
  }
}

variable "create_project" {
  type    = bool
  default = false
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
  description = "Apply-phase WIF identity; limited to Cloud Run administration and runtime-SA use."
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

variable "monthly_budget_usd" {
  type    = number
  default = 50
}

variable "notification_channel_display_names" {
  description = "Display names of independently selected, enabled, VERIFIED Monitoring email channels."
  type        = list(string)
  nullable    = false

  validation {
    condition = (
      length(var.notification_channel_display_names) > 0
      && length(var.notification_channel_display_names) <= 5
      && length(distinct(var.notification_channel_display_names)) == length(var.notification_channel_display_names)
    )
    error_message = "Provide one to five distinct notification channel display names."
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
