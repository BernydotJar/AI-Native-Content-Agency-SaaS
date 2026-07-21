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
  description = "Name of a pre-provisioned Kubernetes Secret containing required individual identity JSON and optional legacy tenant keys. Secret values are never stored in Terraform state."
  type        = string
  default     = "ai-native-content-agency-runtime"

  validation {
    condition     = length(trimspace(var.runtime_auth_existing_secret)) > 0
    error_message = "runtime_auth_existing_secret must not be empty."
  }
}

variable "runtime_auth_tenant_api_keys_key" {
  description = "Optional Secret key containing the legacy tenant-to-API-key JSON object. Use an empty string to disable legacy credentials."
  type        = string
  default     = "tenant-api-keys.json"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]*$", var.runtime_auth_tenant_api_keys_key))
    error_message = "runtime_auth_tenant_api_keys_key must be empty or a valid Secret data key."
  }
}

variable "runtime_auth_identity_credentials_key" {
  description = "Required key within the existing Secret containing individual identity credentials and RBAC roles."
  type        = string
  default     = "identity-credentials.json"

  validation {
    condition     = length(trimspace(var.runtime_auth_identity_credentials_key)) > 0
    error_message = "runtime_auth_identity_credentials_key must not be empty."
  }
}

variable "login_max_failures" {
  description = "Maximum failed authentication attempts for one credential fingerprint within the configured window."
  type        = number
  default     = 5

  validation {
    condition     = var.login_max_failures >= 1 && var.login_max_failures <= 100 && floor(var.login_max_failures) == var.login_max_failures
    error_message = "login_max_failures must be an integer between 1 and 100."
  }
}

variable "login_source_max_failures" {
  description = "Higher failure threshold for a network source across distinct credential fingerprints."
  type        = number
  default     = 50

  validation {
    condition     = var.login_source_max_failures >= 1 && var.login_source_max_failures <= 10000 && floor(var.login_source_max_failures) == var.login_source_max_failures
    error_message = "login_source_max_failures must be an integer between 1 and 10000."
  }
}

variable "forwarded_allow_ips" {
  description = "Comma-separated trusted proxy IPs/CIDRs used by Uvicorn when resolving the authentication source. Never use * unless the edge removes untrusted forwarding headers."
  type        = string
  default     = "127.0.0.1"

  validation {
    condition     = length(trimspace(var.forwarded_allow_ips)) > 0
    error_message = "forwarded_allow_ips must not be empty."
  }
}

variable "login_window_seconds" {
  description = "Durable authentication failure window in seconds."
  type        = number
  default     = 300

  validation {
    condition     = var.login_window_seconds >= 10 && var.login_window_seconds <= 86400 && floor(var.login_window_seconds) == var.login_window_seconds
    error_message = "login_window_seconds must be an integer between 10 and 86400."
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
