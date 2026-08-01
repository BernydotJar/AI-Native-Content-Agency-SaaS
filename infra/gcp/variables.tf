variable "project_id" {
  description = "Existing Google Cloud project ID. Project creation and billing attachment stay outside this module."
  type        = string

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", var.project_id))
    error_message = "project_id must be a valid 6-30 character Google Cloud project ID."
  }
}

variable "project_number" {
  description = "Numeric Google Cloud project number used to scope the billing budget."
  type        = string
  default     = ""

  validation {
    condition     = !var.enable_bootstrap || can(regex("^[1-9][0-9]{5,19}$", var.project_number))
    error_message = "enable_bootstrap requires the numeric Google Cloud project number."
  }
}

variable "billing_account_id" {
  description = "Open billing account ID used only to create a project-scoped budget."
  type        = string
  default     = ""

  validation {
    condition     = !var.enable_bootstrap || can(regex("^[0-9A-F]{6}-[0-9A-F]{6}-[0-9A-F]{6}$", var.billing_account_id))
    error_message = "enable_bootstrap requires a billing account ID such as 012345-ABCDEF-6789AB."
  }
}

variable "monthly_budget_units" {
  description = "Monthly budget in whole units of the billing account currency. Thresholds are fixed at 5%, 25% and 100%."
  type        = number
  default     = 0

  validation {
    condition     = !var.enable_bootstrap || (var.monthly_budget_units >= 1 && var.monthly_budget_units <= 100000000 && floor(var.monthly_budget_units) == var.monthly_budget_units)
    error_message = "enable_bootstrap requires monthly_budget_units to be a positive whole amount in the billing account currency."
  }
}

variable "region" {
  description = "Google Cloud region for regional resources."
  type        = string
  default     = "us-central1"

  validation {
    condition     = can(regex("^[a-z]+-[a-z]+[0-9]+$", var.region))
    error_message = "region must look like us-central1."
  }
}

variable "environment" {
  description = "Deployment environment label."
  type        = string
  default     = "staging"

  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "environment must be staging or production."
  }
}

variable "github_repository" {
  description = "Exact GitHub owner/repository allowed to exchange OIDC credentials."
  type        = string
  default     = "BernydotJar/AI-Native-Content-Agency-SaaS"

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must use owner/repository form."
  }
}

variable "github_ref" {
  description = "Exact Git ref allowed to impersonate the deployer through GitHub OIDC."
  type        = string
  default     = "refs/heads/main"

  validation {
    condition     = can(regex("^refs/heads/[A-Za-z0-9._/-]+$", var.github_ref))
    error_message = "github_ref must be an exact refs/heads/... value."
  }
}

variable "enable_bootstrap" {
  description = "Create APIs, service accounts, Artifact Registry, Secret Manager containers and GitHub WIF. False keeps plan at zero resources."
  type        = bool
  default     = false
}

variable "enable_cloud_sql" {
  description = "Create the bounded PostgreSQL Cloud SQL pilot instance. Requires bootstrap and an approved estimate within the hard monthly cap."
  type        = bool
  default     = false

  validation {
    condition = !var.enable_cloud_sql || (
      var.enable_bootstrap &&
      can(regex("^[0-9a-f]{64}$", var.cost_review_receipt_sha256)) &&
      var.authorized_monthly_cost_cap_units > 0 &&
      var.reviewed_monthly_cost_estimate_units > 0 &&
      var.reviewed_monthly_cost_estimate_units <= var.authorized_monthly_cost_cap_units &&
      var.monthly_budget_units <= var.authorized_monthly_cost_cap_units
    )
    error_message = "enable_cloud_sql requires bootstrap, explicit cost approval, a positive reviewed estimate within the authorized monthly cap, and a budget no higher than that cap."
  }
}

variable "cost_review_receipt_sha256" {
  description = "SHA-256 of the reviewed all-in cost evidence and approval. The receipt is metadata only and must not contain credentials."
  type        = string
  default     = ""

  validation {
    condition     = var.cost_review_receipt_sha256 == "" || can(regex("^[0-9a-f]{64}$", var.cost_review_receipt_sha256))
    error_message = "cost_review_receipt_sha256 must be empty or a 64-character lowercase SHA-256 value."
  }
}

variable "authorized_monthly_cost_cap_units" {
  description = "Hard operator-authorized monthly ceiling in whole billing-account currency units."
  type        = number
  default     = 0

  validation {
    condition     = var.authorized_monthly_cost_cap_units >= 0 && floor(var.authorized_monthly_cost_cap_units) == var.authorized_monthly_cost_cap_units
    error_message = "authorized_monthly_cost_cap_units must be a non-negative whole amount."
  }
}

variable "reviewed_monthly_cost_estimate_units" {
  description = "Fresh reviewed all-in monthly estimate in whole billing-account currency units."
  type        = number
  default     = 0

  validation {
    condition     = var.reviewed_monthly_cost_estimate_units >= 0 && floor(var.reviewed_monthly_cost_estimate_units) == var.reviewed_monthly_cost_estimate_units
    error_message = "reviewed_monthly_cost_estimate_units must be a non-negative whole amount."
  }
}

variable "cloud_sql_instance_name" {
  description = "Cloud SQL instance name for the pilot."
  type        = string
  default     = "campaignos-pilot"

  validation {
    condition     = can(regex("^[a-z]([-a-z0-9]{0,96}[a-z0-9])?$", var.cloud_sql_instance_name))
    error_message = "cloud_sql_instance_name must be a valid lowercase Cloud SQL instance name."
  }
}

variable "cloud_sql_database_name" {
  description = "Application database created inside the pilot Cloud SQL instance."
  type        = string
  default     = "agency"

  validation {
    condition     = can(regex("^[a-z][a-z0-9_]{0,62}$", var.cloud_sql_database_name))
    error_message = "cloud_sql_database_name must be a bounded lowercase PostgreSQL identifier."
  }
}

variable "cloud_sql_tier" {
  description = "Reviewed Cloud SQL machine tier. db-f1-micro is the minimum shared-core pilot tier, not a production availability claim."
  type        = string
  default     = "db-f1-micro"

  validation {
    condition     = contains(["db-f1-micro", "db-g1-small"], var.cloud_sql_tier) || can(regex("^db-custom-[1-9][0-9]*-[1-9][0-9]*$", var.cloud_sql_tier))
    error_message = "cloud_sql_tier must be an allowed shared-core or explicit custom PostgreSQL tier."
  }
}

variable "cloud_sql_disk_size_gb" {
  description = "Initial PD-SSD size in GiB. Cloud SQL does not permit shrinking."
  type        = number
  default     = 10

  validation {
    condition     = var.cloud_sql_disk_size_gb >= 10 && var.cloud_sql_disk_size_gb <= 100 && floor(var.cloud_sql_disk_size_gb) == var.cloud_sql_disk_size_gb
    error_message = "cloud_sql_disk_size_gb must be a whole number from 10 through 100."
  }
}

variable "cloud_sql_disk_autoresize_limit_gb" {
  description = "Finite storage autoresize ceiling in GiB; zero/unbounded is forbidden."
  type        = number
  default     = 20

  validation {
    condition     = var.cloud_sql_disk_autoresize_limit_gb >= var.cloud_sql_disk_size_gb && var.cloud_sql_disk_autoresize_limit_gb <= 100 && floor(var.cloud_sql_disk_autoresize_limit_gb) == var.cloud_sql_disk_autoresize_limit_gb
    error_message = "cloud_sql_disk_autoresize_limit_gb must be a whole number between the initial disk size and 100."
  }
}

variable "cloud_sql_backup_start_time" {
  description = "UTC start time for the automated backup window."
  type        = string
  default     = "03:00"

  validation {
    condition     = can(regex("^(?:[01][0-9]|2[0-3]):[0-5][0-9]$", var.cloud_sql_backup_start_time))
    error_message = "cloud_sql_backup_start_time must use 24-hour HH:MM UTC form."
  }
}

variable "cloud_sql_backup_retention_count" {
  description = "Number of automated backups retained by Cloud SQL."
  type        = number
  default     = 7

  validation {
    condition     = var.cloud_sql_backup_retention_count >= 7 && var.cloud_sql_backup_retention_count <= 14 && floor(var.cloud_sql_backup_retention_count) == var.cloud_sql_backup_retention_count
    error_message = "cloud_sql_backup_retention_count must be a whole number from 7 through 14."
  }
}

variable "cloud_sql_deletion_protection" {
  description = "Protect the pilot database from Terraform deletion. Disable only through a separately reviewed teardown."
  type        = bool
  default     = true
}

variable "schema_initialization_receipt_sha256" {
  description = "SHA-256 of the separately approved schema/role initialization and runtime-validation receipt. No credential material belongs here."
  type        = string
  default     = ""

  validation {
    condition     = !var.enable_cloud_run || can(regex("^[0-9a-f]{64}$", var.schema_initialization_receipt_sha256))
    error_message = "enable_cloud_run requires a 64-character lowercase SHA-256 schema initialization receipt."
  }
}

variable "enable_cloud_run" {
  description = "Create the Cloud Run service. Requires bootstrap, Cloud SQL, immutable image, schema receipt and pinned minimal secret versions."
  type        = bool
  default     = false

  validation {
    condition     = !var.enable_cloud_run || (var.enable_bootstrap && var.enable_cloud_sql)
    error_message = "enable_cloud_run requires enable_bootstrap=true and enable_cloud_sql=true."
  }
}

variable "allow_unauthenticated" {
  description = "Grant roles/run.invoker to allUsers. Keep false until the staging security review is complete."
  type        = bool
  default     = false

  validation {
    condition     = !var.allow_unauthenticated || var.enable_cloud_run
    error_message = "allow_unauthenticated requires enable_cloud_run=true."
  }
}

variable "service_name" {
  description = "Cloud Run service name."
  type        = string
  default     = "campaignos-staging"

  validation {
    condition     = can(regex("^[a-z]([-a-z0-9]{0,47}[a-z0-9])?$", var.service_name))
    error_message = "service_name must be a valid Cloud Run service name up to 49 characters."
  }
}

variable "artifact_repository_id" {
  description = "Artifact Registry Docker repository ID."
  type        = string
  default     = "campaignos"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,62}$", var.artifact_repository_id))
    error_message = "artifact_repository_id must be 3-63 lowercase letters, digits or hyphens."
  }
}

variable "runtime_service_account_id" {
  description = "User-managed identity used by Cloud Run."
  type        = string
  default     = "campaignos-runtime"
}

variable "deployer_service_account_id" {
  description = "User-managed identity impersonated by GitHub Actions through WIF."
  type        = string
  default     = "campaignos-deployer"
}

variable "workload_identity_pool_id" {
  description = "Workload Identity Pool ID used by GitHub Actions."
  type        = string
  default     = "github-actions"
}

variable "workload_identity_provider_id" {
  description = "OIDC provider ID inside the GitHub Workload Identity Pool."
  type        = string
  default     = "github"
}

variable "container_image" {
  description = "Immutable Artifact Registry image reference including @sha256 digest."
  type        = string
  default     = ""

  validation {
    condition = !var.enable_cloud_run || can(regex(
      "^[a-z0-9-]+-docker\\.pkg\\.dev/[a-z][a-z0-9-]{4,28}[a-z0-9]/[a-z][a-z0-9-]{2,62}/[^@]+@sha256:[0-9a-f]{64}$",
      var.container_image,
    ))
    error_message = "enable_cloud_run requires an immutable Artifact Registry image reference pinned with @sha256."
  }
}

variable "min_instance_count" {
  description = "Minimum Cloud Run instances. Zero preserves scale-to-zero for the pilot."
  type        = number
  default     = 0

  validation {
    condition     = var.min_instance_count == 0
    error_message = "The pilot requires min_instance_count=0 to preserve scale-to-zero."
  }
}

variable "max_instance_count" {
  description = "Maximum Cloud Run instances used as a cost and blast-radius guard."
  type        = number
  default     = 2

  validation {
    condition     = var.max_instance_count >= 1 && var.max_instance_count <= 2 && floor(var.max_instance_count) == var.max_instance_count
    error_message = "The pilot requires max_instance_count to be 1 or 2."
  }
}

variable "container_cpu" {
  description = "Cloud Run CPU limit."
  type        = string
  default     = "1"

  validation {
    condition     = contains(["0.5", "1", "2"], var.container_cpu)
    error_message = "container_cpu must be 0.5, 1 or 2."
  }
}

variable "container_memory" {
  description = "Cloud Run memory limit."
  type        = string
  default     = "512Mi"

  validation {
    condition     = contains(["512Mi", "1Gi", "2Gi"], var.container_memory)
    error_message = "container_memory must be 512Mi, 1Gi or 2Gi."
  }
}

variable "runtime_environment" {
  description = "Non-secret, fail-closed runtime environment. Sensitive values belong in Secret Manager."
  type        = map(string)
  default = {
    AGENCY_HOST                           = "0.0.0.0"
    AGENCY_POSTGRES_SCHEMA_MODE           = "validate"
    AGENCY_SESSION_COOKIE_SECURE          = "true"
    AGENCY_SESSION_COOKIE_SAMESITE        = "lax"
    AGENCY_SOCIAL_PUBLICATION_ENABLED     = "false"
    AGENCY_POLITICAL_CONTENT_ENABLED      = "false"
    AGENCY_POLITICAL_PUBLICATION_ENABLED  = "false"
    AGENCY_POLITICAL_PAID_MEDIA_ENABLED   = "false"
    AGENCY_MODEL_EXECUTION_ENABLED        = "false"
    AGENCY_MODEL_EFFECT_AUTHORITY_ENABLED = "false"
    FORWARDED_ALLOW_IPS                   = "127.0.0.1"
  }

  validation {
    condition = alltrue([
      for forbidden in [
        "AGENCY_DATABASE_URL",
        "AGENCY_IDENTITY_CREDENTIALS_JSON",
        "AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON",
        "AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID",
        "AGENCY_SOCIAL_TOKEN_ENCRYPTION_KEYS_JSON",
        "AGENCY_SOCIAL_TOKEN_ACTIVE_KEY_ID",
        "AGENCY_X_CONSUMER_KEY",
        "AGENCY_X_CONSUMER_SECRET",
        "AGENCY_INSTAGRAM_APP_ID",
        "AGENCY_INSTAGRAM_APP_SECRET",
      ] : !contains(keys(var.runtime_environment), forbidden)
    ])
    error_message = "runtime_environment must not contain database, identity, token-encryption or provider credentials."
  }
}

variable "secret_environment" {
  description = "Map of environment variable names to Secret Manager secret IDs and pinned numeric versions. Secret values are never managed by Terraform."
  type = map(object({
    secret  = string
    version = string
  }))
  default = {}

  validation {
    condition = alltrue([
      for item in values(var.secret_environment) :
      can(regex("^[a-z][a-z0-9-]{1,253}[a-z0-9]$", item.secret)) &&
      can(regex("^[1-9][0-9]*$", item.version))
    ])
    error_message = "Each secret must use a valid Secret Manager ID and a pinned numeric version; latest is not allowed."
  }

  validation {
    condition = length(setintersection(
      toset(keys(var.secret_environment)),
      toset(keys(var.runtime_environment)),
    )) == 0
    error_message = "secret_environment and runtime_environment must not define the same environment variable."
  }

  validation {
    condition = !var.enable_cloud_run || alltrue([
      for required in [
        "AGENCY_DATABASE_URL",
        "AGENCY_IDENTITY_CREDENTIALS_JSON",
        "AGENCY_AUDIT_CHECKPOINT_SIGNING_KEYS_JSON",
        "AGENCY_AUDIT_CHECKPOINT_ACTIVE_KEY_ID",
      ] : contains(keys(var.secret_environment), required)
    ])
    error_message = "Cloud Run requires pinned database, individual-identity and audit-checkpoint secrets. Disabled social/provider capabilities do not require credentials."
  }

  validation {
    condition = alltrue([
      for item in values(var.secret_environment) : contains(var.managed_secret_ids, item.secret)
    ])
    error_message = "Every injected secret must reference a container in managed_secret_ids."
  }
}

variable "managed_secret_ids" {
  description = "Secret Manager containers created by the bootstrap. Values and versions are added out-of-band through gcloud."
  type        = set(string)
  default = [
    "campaignos-database-url",
    "campaignos-identity-credentials",
    "campaignos-audit-checkpoint-signing-keys",
    "campaignos-audit-checkpoint-active-key-id",
    "campaignos-social-token-encryption-keys",
    "campaignos-social-token-active-key-id",
    "campaignos-x-consumer-key",
    "campaignos-x-consumer-secret",
    "campaignos-instagram-app-id",
    "campaignos-instagram-app-secret",
  ]
}
