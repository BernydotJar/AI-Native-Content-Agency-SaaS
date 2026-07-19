locals {
  environment = "dev"
  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "serviceusage.googleapis.com",
    "sqladmin.googleapis.com",
  ])
  image_pusher_member     = "serviceAccount:${var.image_pusher_service_account_email}"
  runtime_plan_member     = "serviceAccount:${var.runtime_plan_service_account_email}"
  runtime_deployer_member = "serviceAccount:${var.runtime_deployer_service_account_email}"
  runtime_project_roles = toset([
    "roles/cloudsql.client",
    "roles/cloudsql.instanceUser",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])
  runtime_deployer_project_roles = toset([
    "roles/cloudsql.viewer",
    "roles/iam.securityReviewer",
    "roles/logging.viewer",
    "roles/monitoring.viewer",
  ])
  runtime_deployer_permissions = toset([
    "resourcemanager.projects.get",
    "run.executions.get",
    "run.jobs.create",
    "run.jobs.delete",
    "run.jobs.get",
    "run.jobs.getIamPolicy",
    "run.jobs.list",
    "run.jobs.run",
    "run.jobs.update",
    "run.locations.get",
    "run.locations.list",
    "run.operations.get",
    "run.services.create",
    "run.services.delete",
    "run.services.get",
    "run.services.getIamPolicy",
    "run.services.list",
    "run.services.setIamPolicy",
    "run.services.update",
  ])
}

resource "terraform_data" "authorization_gate" {
  input = var.project_id

  lifecycle {
    precondition {
      condition     = var.organization_id == null || var.folder_id == null
      error_message = "Select at most one project parent: organization_id or folder_id."
    }

  }
}

resource "google_project" "dev" {
  count = var.create_project ? 1 : 0

  project_id          = var.project_id
  name                = "AI Native Content Agency Dev"
  billing_account     = var.billing_account
  org_id              = var.organization_id
  folder_id           = var.folder_id
  auto_create_network = false
  labels              = var.labels
  deletion_policy     = "PREVENT"

  depends_on = [terraform_data.authorization_gate]
}

module "services" {
  source = "../../modules/project_services"

  project_id = var.project_id
  services   = local.required_services

  depends_on = [google_project.dev]
}

data "google_project" "target" {
  project_id = var.project_id

  depends_on = [google_project.dev]
}

resource "google_service_account" "runtime" {
  project      = var.project_id
  account_id   = "agency-runtime-dev"
  display_name = "Agency control plane dev runtime"
  description  = "Runtime-only identity; no service-account key is created."

  depends_on = [module.services]
}

resource "google_project_iam_member" "runtime_plan" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = local.runtime_plan_member

  depends_on = [module.services]
}

resource "google_project_iam_member" "runtime_deployer" {
  for_each = local.runtime_deployer_project_roles

  project = var.project_id
  role    = each.value
  member  = local.runtime_deployer_member

  depends_on = [module.services]
}

resource "google_project_iam_custom_role" "runtime_deployer" {
  project     = var.project_id
  role_id     = "agencyRuntimeDeployer"
  title       = "Agency runtime deployer"
  description = "Exact Cloud Run service/job deployment and migration execution permissions."
  permissions = local.runtime_deployer_permissions

  depends_on = [module.services]
}

resource "google_project_iam_member" "runtime_deployer_custom" {
  project = var.project_id
  role    = google_project_iam_custom_role.runtime_deployer.name
  member  = local.runtime_deployer_member
}

resource "google_service_account_iam_member" "runtime_deployer_user" {
  service_account_id = google_service_account.runtime.name
  role               = "roles/iam.serviceAccountUser"
  member             = local.runtime_deployer_member
}

resource "google_project_iam_member" "runtime" {
  for_each = local.runtime_project_roles

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.runtime.email}"

  depends_on = [module.services]
}

module "artifact_registry" {
  source = "../../modules/artifact_registry"

  project_id    = var.project_id
  location      = var.region
  repository_id = "agency-images"
  labels        = var.labels

  depends_on = [module.services]
}

resource "google_artifact_registry_repository_iam_member" "image_pusher" {
  project    = var.project_id
  location   = var.region
  repository = module.artifact_registry.repository_id
  role       = "roles/artifactregistry.writer"
  member     = local.image_pusher_member
}

resource "google_artifact_registry_repository_iam_member" "runtime_deployer_reader" {
  project    = var.project_id
  location   = var.region
  repository = module.artifact_registry.repository_id
  role       = "roles/artifactregistry.reader"
  member     = local.runtime_deployer_member
}

module "cloud_sql" {
  source = "../../modules/cloud_sql"

  project_id                    = var.project_id
  region                        = var.region
  runtime_service_account_email = google_service_account.runtime.email
  labels                        = var.labels

  depends_on = [
    module.services,
    google_project_iam_member.runtime,
  ]
}

module "observability" {
  source = "../../modules/observability"

  project_id                         = var.project_id
  project_number                     = data.google_project.target.number
  cloud_run_service_name             = "agency-control-plane-dev"
  enable_cloud_run_alert             = true
  billing_account                    = var.billing_account
  monthly_budget_usd                 = var.monthly_budget_usd
  notification_channel_display_names = var.notification_channel_display_names
  labels                             = var.labels

  depends_on = [module.services]
}
