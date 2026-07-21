variable "kubeconfig_path" {
  description = "Path to the kubeconfig used for the target cluster."
  type        = string
  default     = "~/.kube/config"
}

variable "namespace" {
  description = "Kubernetes namespace for the application."
  type        = string
  default     = "ai-native-content-agency"
}

variable "create_namespace" {
  description = "Create the namespace in this module. Keep false when a platform layer pre-provisions the namespace and runtime Secret."
  type        = bool
  default     = false
}

variable "image_repository" {
  description = "Container image repository."
  type        = string
  default     = "ai-native-content-agency"
}

variable "image_tag" {
  description = "Immutable image tag."
  type        = string
  default     = "local"
}


variable "replica_count" {
  description = "Application replica count. Keep at 1 while SQLite persistence is enabled."
  type        = number
  default     = 1

  validation {
    condition     = var.replica_count >= 1 && floor(var.replica_count) == var.replica_count
    error_message = "replica_count must be a positive integer."
  }
}

variable "persistence_enabled" {
  description = "Provision the chart PVC and use durable SQLite storage."
  type        = bool
  default     = true
}

variable "runtime_auth_existing_secret" {
  description = "Name of a pre-provisioned Kubernetes Secret containing tenant API key JSON. Secret values are never stored in Terraform state."
  type        = string
  default     = "ai-native-content-agency-runtime"

  validation {
    condition     = length(trimspace(var.runtime_auth_existing_secret)) > 0
    error_message = "runtime_auth_existing_secret must not be empty."
  }
}

variable "runtime_auth_tenant_api_keys_key" {
  description = "Key within the existing Secret that contains the tenant-to-API-key JSON object."
  type        = string
  default     = "tenant-api-keys.json"

  validation {
    condition     = length(trimspace(var.runtime_auth_tenant_api_keys_key)) > 0
    error_message = "runtime_auth_tenant_api_keys_key must not be empty."
  }
}

variable "session_cookie_secure" {
  description = "Require HTTPS before browsers send the HttpOnly session cookie. Disable only for isolated local HTTP validation."
  type        = bool
  default     = true
}

variable "helm_wait" {
  description = "Wait for Kubernetes workloads to become ready. Disable only for API-only control-plane validation."
  type        = bool
  default     = true
}

variable "helm_timeout_seconds" {
  description = "Maximum Helm release wait duration."
  type        = number
  default     = 300

  validation {
    condition     = var.helm_timeout_seconds >= 30 && floor(var.helm_timeout_seconds) == var.helm_timeout_seconds
    error_message = "helm_timeout_seconds must be an integer of at least 30."
  }
}
