resource "google_artifact_registry_repository" "app" {
  count = var.enable_bootstrap ? 1 : 0

  project                = var.project_id
  location               = var.region
  repository_id          = var.artifact_repository_id
  description            = "Immutable CampaignOS application images"
  format                 = "DOCKER"
  labels                 = local.labels
  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "delete-older-than-30d"
    action = "DELETE"

    condition {
      tag_state  = "ANY"
      older_than = "2592000s"
    }
  }

  cleanup_policies {
    id     = "keep-five-most-recent"
    action = "KEEP"

    most_recent_versions {
      keep_count = 5
    }
  }

  depends_on = [google_project_service.required]
}
