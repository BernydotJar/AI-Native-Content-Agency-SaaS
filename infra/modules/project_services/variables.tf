variable "project_id" {
  description = "Explicit target project; the active gcloud project is never inherited."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid, explicit Google Cloud project ID."
  }
}

variable "services" {
  description = "APIs required by implemented behavior only."
  type        = set(string)
  nullable    = false
}
