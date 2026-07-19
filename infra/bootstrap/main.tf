locals {
  required_services = toset([
    "cloudresourcemanager.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "terraform_data" "authorization_gate" {
  input = var.project_id

  lifecycle {
    precondition {
      condition     = !var.create_project || var.billing_account != null
      error_message = "Creating the bootstrap project requires one explicitly selected open billing account."
    }

    precondition {
      condition     = var.organization_id == null || var.folder_id == null
      error_message = "Select at most one project parent: organization_id or folder_id."
    }
  }
}

resource "google_project" "bootstrap" {
  count = var.create_project ? 1 : 0

  project_id          = var.project_id
  name                = "AI Native Agency Bootstrap"
  billing_account     = var.billing_account
  org_id              = var.organization_id
  folder_id           = var.folder_id
  auto_create_network = false
  labels              = var.labels
  deletion_policy     = "PREVENT"

  depends_on = [terraform_data.authorization_gate]
}

module "services" {
  source = "../modules/project_services"

  project_id = var.project_id
  services   = local.required_services

  depends_on = [google_project.bootstrap]
}

resource "google_storage_bucket" "terraform_state" {
  project                     = var.project_id
  name                        = var.state_bucket_name
  location                    = upper(var.region)
  force_destroy               = false
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  labels                      = var.labels

  versioning {
    enabled = true
  }

  soft_delete_policy {
    retention_duration_seconds = 604800
  }

  retention_policy {
    is_locked        = false
    retention_period = 86400
  }

  lifecycle_rule {
    condition {
      age                   = 30
      num_newer_versions    = 10
      with_state            = "ARCHIVED"
      matches_storage_class = ["STANDARD"]
    }

    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  depends_on = [module.services]
}

module "github_wif" {
  source = "../modules/github_wif"

  project_id              = var.project_id
  github_repository_owner = var.github_repository_owner
  github_repository       = var.github_repository
  github_allowed_ref      = var.github_allowed_ref
  github_workflow_path    = var.github_workflow_path
  labels                  = var.labels

  depends_on = [module.services]
}

resource "google_project_iam_custom_role" "terraform_state_lister" {
  project     = var.project_id
  role_id     = "terraformStateLister"
  title       = "Terraform state object lister"
  description = "Lists state object names without granting object content or mutation access."
  permissions = ["storage.objects.list"]

  depends_on = [module.services]
}

resource "google_project_iam_custom_role" "terraform_state_reader" {
  project     = var.project_id
  role_id     = "terraformStateReader"
  title       = "Terraform state object reader"
  description = "Reads only condition-selected foundation or runtime state objects."
  permissions = ["storage.objects.get"]

  depends_on = [module.services]
}

resource "google_project_iam_custom_role" "terraform_state_locker" {
  project     = var.project_id
  role_id     = "terraformStateLocker"
  title       = "Terraform runtime state locker"
  description = "Creates and deletes only condition-selected Terraform lock objects."
  permissions = [
    "storage.objects.create",
    "storage.objects.delete",
  ]

  depends_on = [module.services]
}

resource "google_storage_bucket_iam_member" "terraform_state_list" {
  for_each = toset(["plan", "apply"])

  bucket = google_storage_bucket.terraform_state.name
  role   = google_project_iam_custom_role.terraform_state_lister.name
  member = "serviceAccount:${module.github_wif.service_account_emails[each.value]}"
}

resource "google_storage_bucket_iam_member" "terraform_state_read" {
  for_each = {
    plan = join(" || ", [
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.terraform_state.name}/objects/environments/dev/')",
      "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.terraform_state.name}/objects/environments/dev-runtime/')",
    ])
    apply = "resource.name.startsWith('projects/_/buckets/${google_storage_bucket.terraform_state.name}/objects/environments/dev/')"
  }

  bucket = google_storage_bucket.terraform_state.name
  role   = google_project_iam_custom_role.terraform_state_reader.name
  member = "serviceAccount:${module.github_wif.service_account_emails[each.key]}"

  condition {
    title       = "${each.key}-state-read"
    description = "Limit state content reads to the states required by this phase."
    expression  = "resource.type == 'storage.googleapis.com/Object' && (${each.value})"
  }
}

resource "google_storage_bucket_iam_member" "terraform_plan_lock" {
  bucket = google_storage_bucket.terraform_state.name
  role   = google_project_iam_custom_role.terraform_state_locker.name
  member = "serviceAccount:${module.github_wif.service_account_emails.plan}"

  condition {
    title       = "plan-runtime-lock-only"
    description = "The plan phase can only create/delete the runtime backend lock object."
    expression  = "resource.type == 'storage.googleapis.com/Object' && resource.name.startsWith('projects/_/buckets/${google_storage_bucket.terraform_state.name}/objects/environments/dev-runtime/') && resource.name.endsWith('.tflock')"
  }
}

resource "google_storage_bucket_iam_member" "terraform_apply_runtime" {
  bucket = google_storage_bucket.terraform_state.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${module.github_wif.service_account_emails.apply}"

  condition {
    title       = "apply-runtime-state-only"
    description = "The apply phase can mutate only the narrow dev-runtime backend prefix."
    expression  = "resource.type == 'storage.googleapis.com/Object' && resource.name.startsWith('projects/_/buckets/${google_storage_bucket.terraform_state.name}/objects/environments/dev-runtime/')"
  }
}
