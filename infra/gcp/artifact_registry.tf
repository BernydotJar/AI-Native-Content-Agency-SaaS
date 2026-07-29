resource "google_artifact_registry_repository" "app" {
  count = var.enable_bootstrap ? 1 : 0

  project       = var.project_id
  location      = var.region
  repository_id = var.artifact_repository_id
  description   = "Immutable CampaignOS application images"
  format        = "DOCKER"
  labels        = local.labels

  depends_on = [google_project_service.required]
}
