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
  description = "Application replica count. SQLite requires one; PostgreSQL supports multiple replicas."
  type        = number
  default     = 1

  validation {
    condition     = var.replica_count >= 1 && floor(var.replica_count) == var.replica_count
    error_message = "replica_count must be a positive integer."
  }
}

variable "prometheus_rule_enabled" {
  description = "Render the PrometheusRule for an existing Prometheus Operator. This module never installs the operator."
  type        = bool
  default     = false
}

variable "persistence_enabled" {
  description = "Provision the chart PVC when storage_backend is sqlite. Ignored by PostgreSQL-backed pods."
  type        = bool
  default     = true
}

variable "storage_backend" {
  description = "Runtime state backend: sqlite for local/single-writer operation or postgresql for shared multi-replica state."
  type        = string
  default     = "sqlite"

  validation {
    condition     = contains(["sqlite", "postgresql"], var.storage_backend)
    error_message = "storage_backend must be sqlite or postgresql."
  }
}

variable "postgresql_existing_secret" {
  description = "Name of a pre-provisioned Kubernetes Secret containing the PostgreSQL connection URL. The URL value is never stored in Terraform state."
  type        = string
  default     = ""

  validation {
    condition     = var.postgresql_existing_secret == "" || can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.postgresql_existing_secret))
    error_message = "postgresql_existing_secret must be empty or a valid Kubernetes Secret name."
  }
}

variable "postgresql_database_url_key" {
  description = "Key within postgresql_existing_secret containing the postgresql:// connection URL."
  type        = string
  default     = "database-url"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+$", var.postgresql_database_url_key))
    error_message = "postgresql_database_url_key must be a valid Secret data key."
  }
}

variable "postgresql_pool_min_size" {
  description = "Minimum Psycopg connection-pool size per application replica."
  type        = number
  default     = 1

  validation {
    condition     = var.postgresql_pool_min_size >= 1 && var.postgresql_pool_min_size <= 100 && floor(var.postgresql_pool_min_size) == var.postgresql_pool_min_size
    error_message = "postgresql_pool_min_size must be an integer between 1 and 100."
  }
}

variable "postgresql_pool_max_size" {
  description = "Maximum Psycopg connection-pool size per application replica. Coordinate replica_count times this value with the database connection limit."
  type        = number
  default     = 10

  validation {
    condition     = var.postgresql_pool_max_size >= 1 && var.postgresql_pool_max_size <= 100 && floor(var.postgresql_pool_max_size) == var.postgresql_pool_max_size
    error_message = "postgresql_pool_max_size must be an integer between 1 and 100."
  }
}

variable "postgresql_connect_timeout_seconds" {
  description = "Maximum startup wait for the PostgreSQL pool to establish a healthy connection."
  type        = number
  default     = 15

  validation {
    condition     = var.postgresql_connect_timeout_seconds >= 1 && var.postgresql_connect_timeout_seconds <= 300 && floor(var.postgresql_connect_timeout_seconds) == var.postgresql_connect_timeout_seconds
    error_message = "postgresql_connect_timeout_seconds must be an integer between 1 and 300."
  }
}

variable "postgresql_schema_mode" {
  description = "Schema behavior for long-running PostgreSQL application pods. Only validate is permitted; initialize belongs to an explicit migration command."
  type        = string
  default     = "validate"

  validation {
    condition     = lower(trimspace(var.postgresql_schema_mode)) == "validate"
    error_message = "postgresql_schema_mode must be validate for long-running application pods."
  }
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

variable "public_media_base_url" {
  description = "Optional HTTPS public base URL used for bounded publication-media capabilities."
  type        = string
  default     = ""

  validation {
    condition     = var.public_media_base_url == "" || can(regex("^https://[^?#]+$", var.public_media_base_url))
    error_message = "public_media_base_url must be empty or HTTPS without query or fragment."
  }
}

variable "public_media_ttl_seconds" {
  description = "Lifetime of a public media capability in seconds."
  type        = number
  default     = 86400

  validation {
    condition     = var.public_media_ttl_seconds >= 900 && var.public_media_ttl_seconds <= 604800 && floor(var.public_media_ttl_seconds) == var.public_media_ttl_seconds
    error_message = "public_media_ttl_seconds must be an integer between 900 and 604800."
  }
}

variable "public_media_existing_secret" {
  description = "Optional pre-provisioned Kubernetes Secret containing public-media signing configuration. Secret values never enter Terraform state."
  type        = string
  default     = ""

  validation {
    condition     = var.public_media_existing_secret == "" || can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.public_media_existing_secret))
    error_message = "public_media_existing_secret must be empty or a valid Kubernetes Secret name."
  }
}

variable "public_media_signing_keys_json_key" {
  description = "Secret data-key name containing key-ID to base64url signing-key JSON."
  type        = string
  default     = "public-media-signing-keys.json"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]*$", var.public_media_signing_keys_json_key))
    error_message = "public_media_signing_keys_json_key must be empty or a valid Secret data key."
  }
}

variable "public_media_active_signing_key_id_key" {
  description = "Secret data-key name containing the active public-media signing key ID."
  type        = string
  default     = "public-media-active-signing-key-id"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]*$", var.public_media_active_signing_key_id_key))
    error_message = "public_media_active_signing_key_id_key must be empty or a valid Secret data key."
  }
}

variable "public_media_legacy_signing_key_key" {
  description = "Migration-only Secret data-key name containing the legacy raw signing key. Blank when using the keyring."
  type        = string
  default     = ""

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]*$", var.public_media_legacy_signing_key_key))
    error_message = "public_media_legacy_signing_key_key must be empty or a valid Secret data key."
  }
}

variable "model_execution_enabled" {
  description = "Enables the bounded model gateway. Keep false until provider, privacy and cost controls are approved."
  type        = bool
  default     = false
}

variable "model_effect_authority_enabled" {
  description = "Enables durable model effects on governed run artifacts. Requires model_execution_enabled."
  type        = bool
  default     = false
}

variable "model_provider" {
  description = "Exact allowlisted model provider selected server-side."
  type        = string
  default     = ""

  validation {
    condition     = var.model_provider == "" || contains(["openai", "anthropic", "deepseek", "moonshot", "llama"], lower(trimspace(var.model_provider)))
    error_message = "model_provider must be empty or an allowlisted provider."
  }
}

variable "model_egress_allowed_hosts" {
  description = "Comma-separated exact HTTPS hosts permitted for model egress."
  type        = string
  default     = ""
}

variable "model_max_output_tokens" {
  description = "Maximum output tokens for one governed model effect."
  type        = number
  default     = 512

  validation {
    condition     = var.model_max_output_tokens >= 1 && var.model_max_output_tokens <= 8192 && floor(var.model_max_output_tokens) == var.model_max_output_tokens
    error_message = "model_max_output_tokens must be an integer between 1 and 8192."
  }
}

variable "model_existing_secret" {
  description = "Optional pre-provisioned Kubernetes Secret containing provider API keys. Secret values never enter Terraform state."
  type        = string
  default     = ""

  validation {
    condition     = var.model_existing_secret == "" || can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.model_existing_secret))
    error_message = "model_existing_secret must be empty or a valid Kubernetes Secret name."
  }
}

variable "model_api_key_secret_keys" {
  description = "Data-key names inside model_existing_secret. Values are names only."
  type = object({
    openai    = string
    anthropic = string
    deepseek  = string
    moonshot  = string
    llama     = string
  })
  default = {
    openai    = "openai-api-key"
    anthropic = "anthropic-api-key"
    deepseek  = "deepseek-api-key"
    moonshot  = "moonshot-api-key"
    llama     = "llama-api-key"
  }

  validation {
    condition = alltrue([
      for value in values(var.model_api_key_secret_keys) :
      can(regex("^[A-Za-z0-9._-]+$", value))
    ])
    error_message = "Every model_api_key_secret_keys value must be a valid Secret data key."
  }
}

variable "model_names" {
  description = "Provider-specific model identifiers configured outside the Secret."
  type = object({
    openai    = string
    anthropic = string
    deepseek  = string
    moonshot  = string
    llama     = string
  })
  default = {
    openai    = ""
    anthropic = ""
    deepseek  = ""
    moonshot  = ""
    llama     = ""
  }
}

variable "political_content_enabled" {
  description = "Explicitly enables political-content creation. It does not enable publication or paid activation."
  type        = bool
  default     = false
}

variable "social_publication_enabled" {
  description = "Explicitly enables governed external social publication. Keep false until provider terms, account authorization and release gates are approved."
  type        = bool
  default     = false
}

variable "political_publication_enabled" {
  description = "Separately enables governed political publication. General social publication never implies this authority."
  type        = bool
  default     = false
}

variable "political_paid_media_enabled" {
  description = "Explicit paid-political kill switch. The organic publication endpoint remains unable to execute paid media."
  type        = bool
  default     = false
}

variable "social_existing_secret" {
  description = "Optional pre-provisioned Kubernetes Secret containing X and Instagram app credentials. Secret values never enter Terraform state."
  type        = string
  default     = ""

  validation {
    condition     = var.social_existing_secret == "" || can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.social_existing_secret))
    error_message = "social_existing_secret must be empty or a valid Kubernetes Secret name."
  }
}

variable "x_consumer_key_secret_key" {
  description = "Key within social_existing_secret containing the X Consumer Key or OAuth client ID."
  type        = string
  default     = "x-consumer-key"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+$", var.x_consumer_key_secret_key))
    error_message = "x_consumer_key_secret_key must be a valid Secret data key."
  }
}

variable "x_consumer_secret_secret_key" {
  description = "Key within social_existing_secret containing the X Consumer Secret or OAuth client secret."
  type        = string
  default     = "x-consumer-secret"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+$", var.x_consumer_secret_secret_key))
    error_message = "x_consumer_secret_secret_key must be a valid Secret data key."
  }
}

variable "x_redirect_uri" {
  description = "Registered X OAuth callback URI. Leave empty until the app callback is configured."
  type        = string
  default     = ""

  validation {
    condition = (
      var.x_redirect_uri == "" ||
      can(regex("^https://[^?#]+$", var.x_redirect_uri)) ||
      can(regex("^http://(127\\.0\\.0\\.1|localhost)(:[0-9]+)?/[^?#]*$", var.x_redirect_uri))
    )
    error_message = "x_redirect_uri must be empty, HTTPS, or loopback HTTP without query or fragment."
  }
}

variable "instagram_app_id_secret_key" {
  description = "Key within social_existing_secret containing the Instagram App ID."
  type        = string
  default     = "instagram-app-id"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+$", var.instagram_app_id_secret_key))
    error_message = "instagram_app_id_secret_key must be a valid Secret data key."
  }
}

variable "instagram_app_secret_secret_key" {
  description = "Key within social_existing_secret containing the Instagram App Secret."
  type        = string
  default     = "instagram-app-secret"

  validation {
    condition     = can(regex("^[A-Za-z0-9._-]+$", var.instagram_app_secret_secret_key))
    error_message = "instagram_app_secret_secret_key must be a valid Secret data key."
  }
}

variable "instagram_graph_api_version" {
  description = "Pinned Instagram Graph API version used for Instagram Login publication endpoints."
  type        = string
  default     = "v24.0"

  validation {
    condition     = can(regex("^v[0-9]+\\.[0-9]+$", var.instagram_graph_api_version))
    error_message = "instagram_graph_api_version must use the vN.N format."
  }
}

variable "instagram_redirect_uri" {
  description = "Registered Instagram Business Login callback URI. Leave empty until the app callback is configured."
  type        = string
  default     = ""

  validation {
    condition = (
      var.instagram_redirect_uri == "" ||
      can(regex("^https://[^?#]+$", var.instagram_redirect_uri)) ||
      can(regex("^http://(127\\.0\\.0\\.1|localhost)(:[0-9]+)?/[^?#]*$", var.instagram_redirect_uri))
    )
    error_message = "instagram_redirect_uri must be empty, HTTPS, or loopback HTTP without query or fragment."
  }
}

variable "social_oauth_secret_keys" {
  description = "Data-key names inside social_existing_secret for encryption and optional server-side token bootstrap. Values are names only; secret material never enters Terraform state."
  type = object({
    encryption_keys_json       = string
    active_encryption_key_id   = string
    x_user_access_token        = string
    x_user_access_token_secret = string
    x_account_id               = string
    x_account_username         = string
    instagram_access_token     = string
    instagram_account_id       = string
    instagram_account_username = string
    instagram_token_expires_at = string
  })
  default = {
    encryption_keys_json       = "social-token-encryption-keys.json"
    active_encryption_key_id   = "social-token-active-key-id"
    x_user_access_token        = "x-user-access-token"
    x_user_access_token_secret = "x-user-access-token-secret"
    x_account_id               = "x-account-id"
    x_account_username         = "x-account-username"
    instagram_access_token     = "instagram-access-token"
    instagram_account_id       = "instagram-account-id"
    instagram_account_username = "instagram-account-username"
    instagram_token_expires_at = "instagram-token-expires-at"
  }

  validation {
    condition = alltrue([
      for value in values(var.social_oauth_secret_keys) :
      can(regex("^[A-Za-z0-9._-]+$", value))
    ])
    error_message = "Every social_oauth_secret_keys value must be a valid Kubernetes Secret data key."
  }
}

variable "social_bootstrap_tenant_id" {
  description = "Optional tenant receiving pre-issued X/Instagram tokens from the existing Secret. Leave empty when OAuth is used."
  type        = string
  default     = ""

  validation {
    condition     = var.social_bootstrap_tenant_id == "" || can(regex("^[A-Za-z0-9][A-Za-z0-9._:@-]{0,255}$", var.social_bootstrap_tenant_id))
    error_message = "social_bootstrap_tenant_id must be empty or a valid tenant identifier."
  }
}
