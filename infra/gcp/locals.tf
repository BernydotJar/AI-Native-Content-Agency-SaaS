locals {
  labels = {
    application = "campaignos"
    environment = var.environment
    managed_by  = "terraform"
  }

  required_services = toset([
    "artifactregistry.googleapis.com",
    "iam.googleapis.com",
    "iamcredentials.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "serviceusage.googleapis.com",
    "sts.googleapis.com",
  ])

  deployer_project_roles = toset([
    "roles/artifactregistry.writer",
    "roles/run.admin",
    "roles/serviceusage.serviceUsageConsumer",
  ])
}
