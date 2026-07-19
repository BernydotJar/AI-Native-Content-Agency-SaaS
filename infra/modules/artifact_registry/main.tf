resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.location
  repository_id = var.repository_id
  description   = "Private application images deployed by immutable digest to the dev control plane."
  format        = "DOCKER"
  labels        = var.labels

  docker_config {
    # Runtime deployment is bound to a digest. Tags remain removable so the
    # cleanup policy can actually bound storage for uniquely tagged builds.
    immutable_tags = false
  }

  cleanup_policy_dry_run = false

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"

    most_recent_versions {
      keep_count = 20
    }
  }

  cleanup_policies {
    id     = "keep-current-rollback"
    action = "KEEP"

    condition {
      tag_state    = "TAGGED"
      tag_prefixes = ["rollback-current"]
    }
  }

  cleanup_policies {
    id     = "delete-old"
    action = "DELETE"

    condition {
      tag_state  = "ANY"
      older_than = "604800s"
    }
  }
}
