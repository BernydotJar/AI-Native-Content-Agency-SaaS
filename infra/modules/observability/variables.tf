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

variable "labels" {
  type    = map(string)
  default = {}
}
