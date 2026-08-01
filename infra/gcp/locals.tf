locals {
  labels = {
    application = "campaignos"
    environment = var.environment
    managed_by  = "terraform"
  }

  required_services = toset([
    "artifactregistry.googleapis.com",
    "billingbudgets.googleapis.com",
    "cloudbilling.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "sqladmin.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
  ])

  budget_thresholds = toset([0.05, 0.25, 1.0])

  deployer_project_roles = toset([
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/serviceusage.serviceUsageConsumer",
  ])
}
