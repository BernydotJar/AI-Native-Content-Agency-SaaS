resource "google_service_account" "runtime" {
  count = var.enable_bootstrap ? 1 : 0

  project      = var.project_id
  account_id   = var.runtime_service_account_id
  display_name = "CampaignOS ${var.environment} runtime"
  description  = "Least-privilege identity for the CampaignOS Cloud Run service."

  depends_on = [google_project_service.required]
}

resource "google_service_account" "deployer" {
  count = var.enable_bootstrap ? 1 : 0

  project      = var.project_id
  account_id   = var.deployer_service_account_id
  display_name = "CampaignOS GitHub deployer"
  description  = "Keyless GitHub Actions deployment identity through Workload Identity Federation."

  depends_on = [google_project_service.required]
}

resource "google_secret_manager_secret_iam_member" "runtime_secret_accessor" {
  for_each = var.enable_bootstrap ? toset([
    for item in values(var.secret_environment) : item.secret
  ]) : toset([])

  project   = var.project_id
  secret_id = google_secret_manager_secret.runtime[each.key].secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.runtime[0].email}"
}

resource "google_project_iam_member" "runtime_cloud_sql_client" {
  count = var.enable_cloud_sql ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.runtime[0].email}"
}

resource "google_project_iam_member" "deployer_cloud_sql_admin" {
  count = var.enable_cloud_sql ? 1 : 0

  project = var.project_id
  role    = "roles/cloudsql.admin"
  member  = "serviceAccount:${google_service_account.deployer[0].email}"
}

resource "google_project_iam_member" "deployer" {
  for_each = var.enable_bootstrap ? local.deployer_project_roles : toset([])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.deployer[0].email}"
}

resource "google_service_account_iam_member" "deployer_can_act_as_runtime" {
  count = var.enable_bootstrap ? 1 : 0

  service_account_id = google_service_account.runtime[0].name
  role               = "roles/iam.serviceAccountUser"
  member             = "serviceAccount:${google_service_account.deployer[0].email}"
}

resource "google_iam_workload_identity_pool" "github" {
  count = var.enable_bootstrap ? 1 : 0

  project                   = var.project_id
  workload_identity_pool_id = var.workload_identity_pool_id
  display_name              = "GitHub Actions"
  description               = "Keyless CI identity restricted to ${var.github_repository}."

  depends_on = [google_project_service.required]
}

resource "google_iam_workload_identity_pool_provider" "github" {
  count = var.enable_bootstrap ? 1 : 0

  project                            = var.project_id
  workload_identity_pool_id          = google_iam_workload_identity_pool.github[0].workload_identity_pool_id
  workload_identity_pool_provider_id = var.workload_identity_provider_id
  display_name                       = "GitHub repository OIDC"
  description                        = "Accepts tokens only from ${var.github_repository}."

  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.actor"      = "assertion.actor"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == '${var.github_repository}' && assertion.ref == '${var.github_ref}'"

  oidc {
    issuer_uri = "https://token.actions.githubusercontent.com"
  }
}

resource "google_service_account_iam_member" "github_can_impersonate_deployer" {
  count = var.enable_bootstrap ? 1 : 0

  service_account_id = google_service_account.deployer[0].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github[0].name}/attribute.repository/${var.github_repository}"
}
