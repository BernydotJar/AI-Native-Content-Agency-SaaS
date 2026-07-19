variable "project_id" {
  type     = string
  nullable = false
}

variable "pool_id" {
  type    = string
  default = "github-actions"
}

variable "phase_provider_ids" {
  type = map(string)
  default = {
    build = "github-build"
    plan  = "github-plan"
    apply = "github-apply"
  }

  validation {
    condition     = toset(keys(var.phase_provider_ids)) == toset(["build", "plan", "apply"])
    error_message = "phase_provider_ids must define exactly build, plan and apply."
  }
}

variable "phase_service_account_ids" {
  type = map(string)
  default = {
    build = "github-image-dev"
    plan  = "github-plan-dev"
    apply = "github-deploy-dev"
  }

  validation {
    condition = (
      toset(keys(var.phase_service_account_ids)) == toset(["build", "plan", "apply"])
      && length(distinct(values(var.phase_service_account_ids))) == 3
      && alltrue([for account_id in values(var.phase_service_account_ids) : can(regex("^[a-z][a-z0-9-]{4,28}[a-z0-9]$", account_id))])
    )
    error_message = "phase_service_account_ids must define three distinct valid build, plan and apply IDs."
  }
}

variable "phase_environments" {
  type = map(string)
  default = {
    build = "dev-build"
    plan  = "dev-plan"
    apply = "dev"
  }

  validation {
    condition = (
      toset(keys(var.phase_environments)) == toset(["build", "plan", "apply"])
      && length(distinct(values(var.phase_environments))) == 3
      && alltrue([for environment in values(var.phase_environments) : can(regex("^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$", environment))])
    )
    error_message = "phase_environments must define three distinct valid build, plan and apply environments."
  }
}

variable "github_repository_owner" {
  type     = string
  nullable = false

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_repository_owner))
    error_message = "github_repository_owner contains unsupported characters."
  }
}

variable "github_repository_owner_id" {
  description = "Immutable numeric GitHub owner ID from the OIDC repository_owner_id claim."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_owner_id))
    error_message = "github_repository_owner_id must be the immutable numeric GitHub owner ID."
  }
}

variable "github_repository" {
  type     = string
  nullable = false

  validation {
    condition     = can(regex("^[A-Za-z0-9_.-]+$", var.github_repository))
    error_message = "github_repository must be the repository name without an owner."
  }
}

variable "github_repository_id" {
  description = "Immutable numeric GitHub repository ID from the OIDC repository_id claim."
  type        = string
  nullable    = false

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_repository_id))
    error_message = "github_repository_id must be the immutable numeric GitHub repository ID."
  }
}

variable "github_allowed_ref" {
  description = "Exact Git ref allowed to exchange GitHub OIDC tokens."
  type        = string
  default     = "refs/heads/main"

  validation {
    condition     = can(regex("^refs/heads/[A-Za-z0-9._/-]+$", var.github_allowed_ref))
    error_message = "github_allowed_ref must be one exact branch ref."
  }
}

variable "github_workflow_path" {
  description = "Exact direct workflow path used to derive the GitHub workflow_ref claim."
  type        = string
  default     = ".github/workflows/deploy-dev.yml"

  validation {
    condition     = can(regex("^\\.github/workflows/[A-Za-z0-9_.-]+\\.ya?ml$", var.github_workflow_path))
    error_message = "github_workflow_path must identify one workflow below .github/workflows."
  }
}

variable "labels" {
  type    = map(string)
  default = {}
}
