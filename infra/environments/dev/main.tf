locals {
  environment = "dev"
  required_labels = {
    application = "ai-native-content-agency"
    environment = local.environment
    managed_by  = "terraform"
  }
  effective_labels = merge(var.additional_labels, local.required_labels)
  project_provenance = {
    schema_version             = "gcp-project-provenance.v1"
    provisioning_mode          = var.project_provisioning_mode
    project_id                 = var.project_id
    bootstrap_project_id       = var.bootstrap_project_id
    github_repository_owner_id = var.github_repository_owner_id
    github_repository_id       = var.github_repository_id
    adoption                   = var.project_provisioning_mode == "ADOPT_EXISTING" ? var.existing_project_adoption : null
  }
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
  image_pusher_project_roles = toset([
    "roles/run.viewer",
  ])
  runtime_deployer_project_roles = toset([
    "roles/cloudsql.viewer",
    "roles/iam.securityReviewer",
    "roles/logging.viewer",
    "roles/monitoring.viewer",
    "roles/run.servicesInvoker",
  ])
  runtime_deployer_permissions = toset([
    "resourcemanager.projects.get",
    "run.executions.get",
    "run.jobs.create",
    "run.jobs.get",
    "run.jobs.getIamPolicy",
    "run.jobs.list",
    "run.jobs.run",
    "run.jobs.update",
    "run.locations.get",
    "run.locations.list",
    "run.operations.get",
    "run.services.create",
    "run.services.get",
    "run.services.getIamPolicy",
    "run.services.list",
    "run.services.update",
  ])
  rollback_tag_operator_permissions = toset([
    "artifactregistry.tags.create",
    "artifactregistry.tags.update",
  ])
  notification_channel_imports = {
    for channel in nonsensitive(var.notification_channels) :
    channel.key => channel.existing_channel_name
    if channel.provisioning_mode == "ADOPT_EXISTING"
  }
}

resource "terraform_data" "authorization_gate" {
  input = var.project_id

  lifecycle {
    precondition {
      condition     = var.project_id != var.bootstrap_project_id
      error_message = "The dev project_id must differ from the reviewed bootstrap_project_id."
    }

    precondition {
      condition = var.project_provisioning_mode == "CREATE_NEW" ? (
        var.existing_project_adoption == null
        ) : (
        var.existing_project_adoption != null
        && var.existing_project_adoption.project_id == var.project_id
      )
      error_message = "CREATE_NEW forbids adoption metadata; ADOPT_EXISTING requires metadata bound to the exact project_id."
    }

    precondition {
      condition     = var.organization_id == null || var.folder_id == null
      error_message = "Select at most one project parent: organization_id or folder_id."
    }

    precondition {
      condition = (
        var.image_pusher_service_account_email == "github-image-dev@${var.bootstrap_project_id}.iam.gserviceaccount.com"
        && var.runtime_plan_service_account_email == "github-plan-dev@${var.bootstrap_project_id}.iam.gserviceaccount.com"
        && var.runtime_deployer_service_account_email == "github-deploy-dev@${var.bootstrap_project_id}.iam.gserviceaccount.com"
      )
      error_message = "Foundation phase identities must be the exact fixed bootstrap service accounts for image build, runtime plan and runtime apply."
    }

  }
}

resource "google_project" "dev" {
  project_id          = var.project_id
  name                = "AI Native Content Agency Dev"
  billing_account     = var.billing_account
  org_id              = var.organization_id
  folder_id           = var.folder_id
  auto_create_network = false
  labels              = local.effective_labels
  deletion_policy     = "PREVENT"

  depends_on = [terraform_data.authorization_gate]
}

import {
  for_each = var.project_provisioning_mode == "ADOPT_EXISTING" ? toset([var.project_id]) : toset([])

  to = google_project.dev
  id = each.value
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

  depends_on = [module.services, module.observability]
}

resource "google_project_iam_member" "runtime_plan" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = local.runtime_plan_member

  depends_on = [module.services, module.observability]
}

resource "google_project_iam_member" "image_pusher_runtime_reader" {
  for_each = local.image_pusher_project_roles

  project = var.project_id
  role    = each.value
  member  = local.image_pusher_member

  depends_on = [module.services, module.observability]
}

resource "google_project_iam_member" "runtime_deployer" {
  for_each = local.runtime_deployer_project_roles

  project = var.project_id
  role    = each.value
  member  = local.runtime_deployer_member

  depends_on = [module.services, module.observability]
}

resource "google_project_iam_custom_role" "runtime_deployer" {
  project     = var.project_id
  role_id     = "agencyRuntimeDeployer"
  title       = "Agency runtime deployer"
  description = "Exact Cloud Run service/job deployment and migration execution permissions."
  permissions = local.runtime_deployer_permissions

  depends_on = [module.services, module.observability]
}

resource "google_project_iam_member" "runtime_deployer_custom" {
  project = var.project_id
  role    = google_project_iam_custom_role.runtime_deployer.name
  member  = local.runtime_deployer_member
}

resource "google_project_iam_custom_role" "rollback_tag_operator" {
  project     = var.project_id
  role_id     = "agencyRollbackTagOperator"
  title       = "Agency rollback tag operator"
  description = "Create or move the single reviewed rollback tag without uploading or deleting artifacts."
  permissions = local.rollback_tag_operator_permissions

  depends_on = [module.services, module.observability]
}

# Foundation grants project-level invocation only inside the dedicated dev
# project. Routine runtime deployment cannot mutate service IAM or make a
# service public. Destructive service/job permissions are likewise excluded.

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

  depends_on = [module.services, module.observability]
}

module "artifact_registry" {
  source = "../../modules/artifact_registry"

  project_id    = var.project_id
  location      = var.region
  repository_id = "agency-images"
  labels        = local.effective_labels

  depends_on = [module.services, module.observability]
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

resource "google_artifact_registry_repository_iam_member" "runtime_deployer_rollback_tag" {
  project    = var.project_id
  location   = var.region
  repository = module.artifact_registry.repository_id
  role       = google_project_iam_custom_role.rollback_tag_operator.name
  member     = local.runtime_deployer_member
}

resource "google_artifact_registry_repository_iam_member" "runtime_plan_reader" {
  project    = var.project_id
  location   = var.region
  repository = module.artifact_registry.repository_id
  role       = "roles/artifactregistry.reader"
  member     = local.runtime_plan_member
}

module "cloud_sql" {
  source = "../../modules/cloud_sql"

  project_id                    = var.project_id
  region                        = var.region
  runtime_service_account_email = google_service_account.runtime.email
  labels                        = local.effective_labels

  depends_on = [
    module.services,
    google_project_iam_member.runtime,
  ]
}

module "observability" {
  source = "../../modules/observability"

  project_id             = var.project_id
  project_number         = data.google_project.target.number
  cloud_run_service_name = "agency-control-plane-dev"
  enable_cloud_run_alert = true
  billing_account        = var.billing_account
  monthly_budget_usd     = var.monthly_budget_usd
  notification_channels  = var.notification_channels
  labels                 = local.effective_labels

  depends_on = [module.services]
}

import {
  for_each = local.notification_channel_imports

  to = module.observability.google_monitoring_notification_channel.delivery[each.key]
  id = each.value
}
