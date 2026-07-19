variable "project_id" {
  type     = string
  nullable = false
}

variable "project_number" {
  type     = string
  nullable = false
}

variable "cloud_run_service_name" {
  type     = string
  nullable = false
}

variable "enable_cloud_run_alert" {
  type    = bool
  default = true
}

variable "billing_account" {
  description = "Explicitly selected open billing account for the mandatory dev budget."
  type        = string
  nullable    = false
}

variable "monthly_budget_usd" {
  type    = number
  default = 50

  validation {
    condition     = var.monthly_budget_usd >= 10 && var.monthly_budget_usd <= 200
    error_message = "The bounded dev budget must remain between USD 10 and USD 200."
  }
}

variable "notification_channel_display_names" {
  description = "Explicit display names of pre-existing verified Monitoring email channels used for 5xx and budget delivery."
  type        = list(string)
  nullable    = false

  validation {
    condition = (
      length(var.notification_channel_display_names) > 0
      && length(var.notification_channel_display_names) <= 5
      && length(distinct(var.notification_channel_display_names)) == length(var.notification_channel_display_names)
      && alltrue([
        for display_name in var.notification_channel_display_names :
        can(regex("^[A-Za-z0-9][A-Za-z0-9 _.-]{0,62}[A-Za-z0-9]$", display_name))
      ])
    )
    error_message = "Provide one to five distinct explicit Monitoring email channel display names."
  }
}

variable "labels" {
  type    = map(string)
  default = {}
}
