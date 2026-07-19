locals {
  repository   = "${var.github_repository_owner}/${var.github_repository}"
  workflow_ref = "${local.repository}/${var.github_workflow_path}@${var.github_allowed_ref}"
  phase_display_names = {
    build = "GitHub Artifact Registry image builder"
    plan  = "GitHub Terraform runtime planner"
    apply = "GitHub Terraform runtime deployer"
  }
}

resource "google_service_account" "phase" {
  for_each = var.phase_service_account_ids

  project      = var.project_id
  account_id   = each.value
  display_name = local.phase_display_names[each.key]
  description  = "Keyless ${each.key} identity restricted to one repository, ref, environment and workflow."
}

resource "google_iam_workload_identity_pool" "github" {
  project                   = var.project_id
  workload_identity_pool_id = var.pool_id
  display_name              = "GitHub Actions"
  description               = "OIDC identities for the exact repository, ref, environment and workflow only."
}

resource "google_iam_workload_identity_pool_provider" "phase" {
  for_each = var.phase_environments

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = var.phase_provider_ids[each.key]
  display_name                       = "GitHub ${each.key} provider"

  attribute_mapping = merge(
    {
      "google.subject"             = "assertion.sub"
      "attribute.repository"       = "assertion.repository"
      "attribute.repository_owner" = "assertion.repository_owner"
      "attribute.ref"              = "assertion.ref"
      "attribute.ref_type"         = "assertion.ref_type"
      "attribute.environment"      = "assertion.environment"
      "attribute.workflow_ref"     = "assertion.workflow_ref"
    },
    {
      "attribute.repository_id"       = "assertion.repository_id"
      "attribute.repository_owner_id" = "assertion.repository_owner_id"
    },
  )

  attribute_condition = join(" && ", [
    "assertion.repository_owner == '${var.github_repository_owner}'",
    "assertion.repository_owner_id == '${var.github_repository_owner_id}'",
    "assertion.repository == '${local.repository}'",
    "assertion.repository_id == '${var.github_repository_id}'",
    "assertion.ref == '${var.github_allowed_ref}'",
    "assertion.ref_type == 'branch'",
    "assertion.environment == '${each.value}'",
    "assertion.workflow_ref == '${local.workflow_ref}'",
  ])

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "phase" {
  for_each = var.phase_service_account_ids

  service_account_id = google_service_account.phase[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member = format(
    "principalSet://iam.googleapis.com/%s/attribute.environment/%s",
    google_iam_workload_identity_pool.github.name,
    var.phase_environments[each.key],
  )
}
